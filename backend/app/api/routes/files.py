"""Загрузка и управление файлами объекта (спецификации, сметы, паспорта)."""

import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_object_access
from app.core.config import get_settings
from app.db.session import get_db
from app.models import ConstructionObject, ObjectFile, SourceItem, User
from app.models.enums import DocKind, ItemSource, ParseStatus
from app.schemas.files import FileRead
from app.storage import get_storage

router = APIRouter(prefix="/objects/{object_id}/files", tags=["files"])

ALLOWED_EXTENSIONS: dict[DocKind, set[str]] = {
    DocKind.SPECIFICATION: {"pdf", "xlsx"},
    DocKind.ESTIMATE: {"xml", "xlsx"},
    DocKind.PASSPORT: {"pdf", "zip"},
    DocKind.OTHER: {"pdf", "xlsx", "xml", "zip"},
}

_MAGIC: dict[str, bytes] = {
    "pdf": b"%PDF",
    "zip": b"PK\x03\x04",
    "xlsx": b"PK\x03\x04",
}
_XML_PREFIX = b"<"


def _magic_matches(ext: str, head: bytes) -> bool:
    if ext in _MAGIC:
        return _MAGIC[ext] in head
    if ext == "xml":
        return head.lstrip().startswith(_XML_PREFIX)
    return True


def _size_limit(ext: str) -> int:
    settings = get_settings()
    return settings.max_zip_size_bytes if ext == "zip" else settings.max_file_size_bytes


def _get_file_or_404(file_id: int, db: Session, obj: ConstructionObject) -> ObjectFile:
    f = db.scalar(select(ObjectFile).where(ObjectFile.id == file_id, ObjectFile.object_id == obj.id))
    if f is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
    return f


@router.get("", response_model=list[FileRead])
def list_files(
    object_id: int,
    kind: DocKind | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> list[ObjectFile]:
    stmt = (
        select(ObjectFile)
        .options(selectinload(ObjectFile.uploader))
        .where(ObjectFile.object_id == obj.id)
    )
    if kind is not None:
        stmt = stmt.where(ObjectFile.kind == kind)
    stmt = stmt.order_by(ObjectFile.created_at.desc())
    return list(db.scalars(stmt))


@router.post("", response_model=FileRead, status_code=status.HTTP_201_CREATED)
def upload_file(
    object_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
    kind: DocKind = Form(DocKind.OTHER),
    file: UploadFile = File(...),
) -> ObjectFile:
    """Загрузка файла на объект. Файл пишется в хранилище, метаданные — в БД."""
    original = file.filename or "file"
    ext = Path(original).suffix.lower().lstrip(".")
    allowed = ALLOWED_EXTENSIONS.get(kind, set())
    if not allowed or ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Для вида «{kind.value}» недопустимый формат .{ext or '?'}",
        )
    limit = _size_limit(ext)

    # 1) Сполим во временный файл: считаем sha256, контролируем лимит и magic bytes
    import hashlib

    tmp = tempfile.NamedTemporaryFile(prefix="stroydoc_up_", delete=False)
    tmp_name = tmp.name
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
                    detail=f"Файл больше допустимого лимита ({limit // (1024 * 1024)} МБ)",
                )
            digest.update(chunk)
            tmp.write(chunk)
        tmp.flush()

        if total == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пустой файл")
        if not _magic_matches(ext, head):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Содержимое не соответствует расширению файла"
            )

        # 2) Дубликат внутри объекта
        sha256 = digest.hexdigest()
        duplicate = db.scalar(
            select(ObjectFile).where(ObjectFile.object_id == obj.id, ObjectFile.sha256 == sha256)
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Такой файл уже загружен на объект"
            )

        # 3) Квота объекта
        used = db.scalar(
            select(func.coalesce(func.sum(ObjectFile.size_bytes), 0)).where(
                ObjectFile.object_id == obj.id
            )
        )
        quota = get_settings().object_storage_quota_bytes
        if (used or 0) + total > quota:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Превышена квота хранилища объекта",
            )

        # 4) Сохраняем в хранилище
        storage = get_storage()
        key = f"{obj.company_id}/{obj.id}/{uuid4().hex}.{ext}"
        tmp.seek(0)
        storage.put_stream(key, tmp, total)

        of = ObjectFile(
            company_id=obj.company_id,
            object_id=obj.id,
            uploader_id=user.id,
            kind=kind,
            original_filename=original,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=total,
            sha256=sha256,
            storage_key=key,
            status=ParseStatus.UPLOADED,
        )
        db.add(of)
        try:
            db.commit()
        except Exception:
            db.rollback()
            storage.delete(key)
            raise
        db.refresh(of)
        return of
    finally:
        tmp.close()
        Path(tmp_name).unlink(missing_ok=True)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> None:
    of = _get_file_or_404(file_id, db, obj)
    storage = get_storage()
    key = of.storage_key
    db.delete(of)
    db.commit()
    try:
        storage.delete(key)
    except Exception:  # noqa: BLE001
        pass  # запись удалена, «сирота» в хранилище — некритично


@router.get("/{file_id}/download")
def download_file(
    file_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> object:
    from fastapi.responses import StreamingResponse

    of = _get_file_or_404(file_id, db, obj)
    storage = get_storage()
    stream = storage.open_stream(of.storage_key)
    filename = of.original_filename.replace('"', "_")
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(stream, media_type=of.content_type, headers=headers)


@router.post("/{file_id}/parse", response_model=FileRead)
def parse_file(
    file_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> ObjectFile:
    """Разбор загруженного файла. MVP: PDF-спецификации (синхронно)."""
    of = _get_file_or_404(file_id, db, obj)
    ext = Path(of.original_filename).suffix.lower().lstrip(".")
    if of.kind != DocKind.SPECIFICATION or ext != "pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Разбор доступен только для PDF-спецификаций",
        )

    of.status = ParseStatus.PARSING
    of.error_message = None
    db.add(of)
    db.commit()

    try:
        from app.parsing.spec_pdf import parse_spec_pdf_bytes

        storage = get_storage()
        with storage.open_stream(of.storage_key) as stream:
            data = stream.read()
        records = parse_spec_pdf_bytes(data)

        # Перезаписываем результат разбора для этого файла
        from sqlalchemy import delete

        db.execute(delete(SourceItem).where(SourceItem.source_file_id == of.id))
        for rec in records:
            from decimal import Decimal

            item = SourceItem(
                object_id=obj.id,
                source_file_id=of.id,
                source=ItemSource.RD,
                row_number=rec["row_number"],
                position=str(rec["position"]) if rec["position"] else None,
                name=str(rec["name"]) if rec["name"] else "",
                mark=str(rec["mark_doc"]) if rec.get("mark_doc") else None,
                product_code=str(rec["product_code"]) if rec.get("product_code") else None,
                supplier=str(rec["supplier"]) if rec.get("supplier") else None,
                unit=str(rec["unit"]) if rec.get("unit") else None,
                quantity=(
                    Decimal(str(rec["quantity_value"]))
                    if rec.get("quantity_value") is not None
                    else None
                ),
                mass=str(rec["mass"]) if rec.get("mass") else None,
                notes=str(rec["notes"]) if rec.get("notes") else None,
            )
            db.add(item)
        of.parsed_items = len(records)
        of.status = ParseStatus.DONE
        db.add(of)
        db.commit()
        db.refresh(of)
        return of
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        of = db.get(ObjectFile, of.id)
        if of is not None:
            of.status = ParseStatus.ERROR
            of.error_message = str(exc)[:1000]
            db.add(of)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось разобрать файл: {exc}",
        ) from exc

