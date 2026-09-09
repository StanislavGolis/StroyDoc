"""Пул документов: паспорта/сертификаты объекта и их привязка к позициям."""

import hashlib
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_object_access
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    ConstructionObject,
    IncomingDoc,
    ObjectFile,
    SourceItem,
    User,
    incoming_doc_item,
)
from app.models.enums import DocKind
from app.schemas.incoming import DocAttachRequest, IncomingDocRead, IncomingDocUpdate
from app.storage import get_storage

router = APIRouter(prefix="/objects/{object_id}/docs", tags=["docs"])


def _get_doc_or_404(doc_id: int, db: Session, obj: ConstructionObject) -> IncomingDoc:
    doc = db.scalar(
        select(IncomingDoc)
        .options(joinedload(IncomingDoc.file))
        .where(IncomingDoc.id == doc_id, IncomingDoc.object_id == obj.id)
    )
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")
    return doc


def _linked_count_subq():
    return (
        select(func.count())
        .select_from(incoming_doc_item)
        .where(incoming_doc_item.c.incoming_doc_id == IncomingDoc.id)
        .scalar_subquery()
    )


@router.get("", response_model=list[IncomingDocRead])
def list_docs(
    object_id: int,
    q: str | None = Query(default=None, max_length=200),
    item_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> list[dict]:
    linked = _linked_count_subq()
    stmt = (
        select(IncomingDoc, linked.label("linked_items"))
        .options(joinedload(IncomingDoc.file))
        .where(IncomingDoc.object_id == obj.id)
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (IncomingDoc.doc_number.ilike(like))
            | (IncomingDoc.doc_title.ilike(like))
            | (IncomingDoc.file.has(ObjectFile.original_filename.ilike(like)))
        )
    if item_id is not None:
        stmt = stmt.where(
            IncomingDoc.id.in_(
                select(incoming_doc_item.c.incoming_doc_id).where(
                    incoming_doc_item.c.source_item_id == item_id
                )
            )
        )
    stmt = stmt.order_by(IncomingDoc.created_at.desc())
    rows = db.execute(stmt).all()
    return [
        {
            "id": d.id,
            "object_id": d.object_id,
            "doc_number": d.doc_number,
            "doc_title": d.doc_title,
            "doc_date": d.doc_date,
            "file_id": d.file_id,
            "original_filename": d.file.original_filename if d.file else None,
            "size_bytes": d.file.size_bytes if d.file else None,
            "linked_items": linked_items,
            "created_at": d.created_at,
        }
        for d, linked_items in rows
    ]

@router.post("", response_model=IncomingDocRead, status_code=status.HTTP_201_CREATED)
def upload_doc(
    object_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
    doc_number: str | None = Form(default=None),
    doc_title: str | None = Form(default=None),
    file: UploadFile = File(...),
) -> dict:
    """Загрузка паспорта/сертификата (PDF) и создание записи документа."""
    original = file.filename or "doc.pdf"
    ext = Path(original).suffix.lower().lstrip(".")
    if ext != "pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Документы пула принимаются только в PDF"
        )
    limit = get_settings().max_file_size_bytes

    tmp = tempfile.NamedTemporaryFile(prefix="stroydoc_doc_", delete=False)
    digest = hashlib.sha256()
    total = 0
    head = b""
    try:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            if total == 0:
                head = chunk[:16]
            total += len(chunk)
            if total > limit:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Файл больше допустимого лимита",
                )
            digest.update(chunk)
            tmp.write(chunk)
        tmp.flush()
        if total == 0 or not head.startswith(b"%PDF"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл не является PDF")
        sha256 = digest.hexdigest()

        existing_file = db.scalar(
            select(ObjectFile).where(
                ObjectFile.object_id == obj.id,
                ObjectFile.sha256 == sha256,
                ObjectFile.kind == DocKind.PASSPORT,
            )
        )
        if existing_file is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Такой документ уже загружен")

        storage = get_storage()
        key = f"{obj.company_id}/{obj.id}/{uuid4().hex}.pdf"
        tmp.seek(0)
        storage.put_stream(key, tmp, total)

        of = ObjectFile(
            company_id=obj.company_id,
            object_id=obj.id,
            uploader_id=user.id,
            kind=DocKind.PASSPORT,
            original_filename=original,
            content_type=file.content_type or "application/pdf",
            size_bytes=total,
            sha256=sha256,
            storage_key=key,
        )
        db.add(of)
        db.flush()
        doc = IncomingDoc(
            company_id=obj.company_id,
            object_id=obj.id,
            file_id=of.id,
            created_by=user.id,
            doc_number=doc_number.strip() if doc_number and doc_number.strip() else None,
            doc_title=doc_title.strip() if doc_title and doc_title.strip() else original,
        )
        db.add(doc)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            storage.delete(key)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Такой документ уже загружен"
            ) from None
        db.refresh(doc)
        return {
            "id": doc.id,
            "object_id": doc.object_id,
            "doc_number": doc.doc_number,
            "doc_title": doc.doc_title,
            "doc_date": doc.doc_date,
            "file_id": doc.file_id,
            "original_filename": original,
            "size_bytes": total,
            "linked_items": 0,
            "created_at": doc.created_at,
        }
    finally:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)


@router.patch("/{doc_id}", response_model=IncomingDocRead)
def update_doc(
    object_id: int,
    doc_id: int,
    body: IncomingDocUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> dict:
    doc = _get_doc_or_404(doc_id, db, obj)
    if body.doc_number is not None:
        doc.doc_number = body.doc_number.strip() or None
    if body.doc_title is not None:
        doc.doc_title = body.doc_title.strip() or None
    if body.doc_date is not None:
        doc.doc_date = body.doc_date
    db.add(doc)
    db.commit()
    db.refresh(doc)
    linked = db.scalar(
        select(func.count())
        .select_from(incoming_doc_item)
        .where(incoming_doc_item.c.incoming_doc_id == doc.id)
    )
    return {
        "id": doc.id,
        "object_id": doc.object_id,
        "doc_number": doc.doc_number,
        "doc_title": doc.doc_title,
        "doc_date": doc.doc_date,
        "file_id": doc.file_id,
        "original_filename": doc.file.original_filename if doc.file else None,
        "size_bytes": doc.file.size_bytes if doc.file else None,
        "linked_items": linked or 0,
        "created_at": doc.created_at,
    }

@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doc(
    object_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> None:
    doc = _get_doc_or_404(doc_id, db, obj)
    key = doc.file.storage_key if doc.file else None
    file_obj = doc.file
    db.execute(sa_delete(incoming_doc_item).where(incoming_doc_item.c.incoming_doc_id == doc.id))
    db.delete(doc)
    db.commit()
    if file_obj is not None:
        try:
            get_storage().delete(key or "")
        except Exception:  # noqa: BLE001
            pass


@router.post("/{doc_id}/attach", response_model=dict)
def attach_doc(
    object_id: int,
    doc_id: int,
    body: DocAttachRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> dict:
    doc = _get_doc_or_404(doc_id, db, obj)
    if not body.item_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не выбраны позиции")
    item_ids = set(body.item_ids)
    found = set(
        db.scalars(select(SourceItem.id).where(SourceItem.object_id == obj.id, SourceItem.id.in_(item_ids)))
    )
    missing = item_ids - found
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Позиции не принадлежат объекту: {sorted(missing)[:5]}",
        )
    for item_id in found:
        exists = db.scalar(
            select(incoming_doc_item.c.source_item_id).where(
                incoming_doc_item.c.incoming_doc_id == doc.id,
                incoming_doc_item.c.source_item_id == item_id,
            )
        )
        if not exists:
            db.execute(
                insert(incoming_doc_item).values(incoming_doc_id=doc.id, source_item_id=item_id)
            )
    db.commit()
    linked = db.scalar(
        select(func.count())
        .select_from(incoming_doc_item)
        .where(incoming_doc_item.c.incoming_doc_id == doc.id)
    )
    return {"linked_items": linked or 0}


@router.post("/{doc_id}/detach", response_model=dict)
def detach_doc(
    object_id: int,
    doc_id: int,
    body: DocAttachRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> dict:
    doc = _get_doc_or_404(doc_id, db, obj)
    if body.item_ids:
        db.execute(
            sa_delete(incoming_doc_item).where(
                incoming_doc_item.c.incoming_doc_id == doc.id,
                incoming_doc_item.c.source_item_id.in_(body.item_ids),
            )
        )
        db.commit()
    linked = db.scalar(
        select(func.count())
        .select_from(incoming_doc_item)
        .where(incoming_doc_item.c.incoming_doc_id == doc.id)
    )
    return {"linked_items": linked or 0}
