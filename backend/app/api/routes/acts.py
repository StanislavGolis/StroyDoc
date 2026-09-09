"""Акты: создание, позиции, статусы, генерация DOCX (черновик для печати)."""

from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_object_access
from app.db.session import get_db
from app.models import Act, ConstructionObject, SourceItem, User, act_item
from app.models.enums import ActType
from app.schemas.acts import (
    ActCreate,
    ActItemsRequest,
    ActRead,
    ActUpdate,
)
from app.schemas.items import SourceItemRead

router = APIRouter(prefix="/objects/{object_id}/acts", tags=["acts"])

ACT_TYPE_LABELS = {
    ActType.AVK: "Акт входного контроля",
    ActType.AOSR: "Акт освидетельствования скрытых работ",
    ActType.VSO: "Ведомость смонтированного оборудования",
    ActType.VR: "Ведомость выполненных работ",
}

ACT_PREFIX = {
    ActType.AVK: "АВК",
    ActType.AOSR: "АОСР",
    ActType.VSO: "ВСО",
    ActType.VR: "ВР",
}


def _get_act_or_404(act_id: int, db: Session, obj: ConstructionObject) -> Act:
    act = db.scalar(
        select(Act).where(Act.id == act_id, Act.object_id == obj.id)
    )
    if act is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Акт не найден")
    return act


def _linked(act_id: int, db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(act_item).where(act_item.c.act_id == act_id)
    ) or 0


def _read(act: Act, db: Session) -> dict:
    return {
        "id": act.id,
        "object_id": act.object_id,
        "act_type": act.act_type,
        "doc_number": act.doc_number,
        "doc_date": act.doc_date,
        "status": act.status,
        "linked_items": _linked(act.id, db),
        "created_at": act.created_at,
    }


@router.get("", response_model=list[ActRead])
def list_acts(
    object_id: int,
    act_type: ActType | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> list[dict]:
    stmt = select(Act).where(Act.object_id == obj.id)
    if act_type is not None:
        stmt = stmt.where(Act.act_type == act_type)
    stmt = stmt.order_by(Act.created_at.desc())
    return [_read(a, db) for a in db.scalars(stmt)]


@router.post("", response_model=ActRead, status_code=status.HTTP_201_CREATED)
def create_act(
    object_id: int,
    body: ActCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> dict:
    # автономер: «АВК-001» и т.п., если номер не указан (считаем ДО вставки)
    auto_number: str | None = None
    if not (body.doc_number and body.doc_number.strip()):
        seq = (
            db.scalar(
                select(func.count()).select_from(Act).where(
                    Act.object_id == obj.id, Act.act_type == body.act_type
                )
            )
            or 0
        ) + 1
        auto_number = f"{ACT_PREFIX.get(body.act_type, body.act_type.value)}-{seq:03d}"

    act = Act(
        company_id=obj.company_id,
        object_id=obj.id,
        act_type=body.act_type,
        doc_number=body.doc_number.strip() if body.doc_number and body.doc_number.strip() else auto_number,
        doc_date=body.doc_date,
        created_by=user.id,
    )
    db.add(act)
    db.flush()
    if body.item_ids:
        found = set(
            db.scalars(
                select(SourceItem.id).where(
                    SourceItem.object_id == obj.id, SourceItem.id.in_(set(body.item_ids))
                )
            )
        )
        for item_id in found:
            db.execute(insert(act_item).values(act_id=act.id, source_item_id=item_id))
    db.commit()
    db.refresh(act)
    return _read(act, db)

@router.patch("/{act_id}", response_model=ActRead)
def update_act(
    object_id: int,
    act_id: int,
    body: ActUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> dict:
    act = _get_act_or_404(act_id, db, obj)
    if body.doc_number is not None:
        act.doc_number = body.doc_number.strip() or None
    if body.doc_date is not None:
        act.doc_date = body.doc_date
    if body.status is not None:
        act.status = body.status
    db.add(act)
    db.commit()
    db.refresh(act)
    return _read(act, db)


@router.get("/{act_id}/items", response_model=list[SourceItemRead])
def act_items(
    object_id: int,
    act_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> list[dict]:
    act = _get_act_or_404(act_id, db, obj)
    items = list(
        db.scalars(
            select(SourceItem)
            .join(act_item, act_item.c.source_item_id == SourceItem.id)
            .where(act_item.c.act_id == act.id)
            .order_by(SourceItem.row_number)
        )
    )
    return [
        SourceItemRead.model_validate(it).model_copy(update={"docs_count": len(it.docs)})
        for it in items
    ]


@router.post("/{act_id}/items", response_model=dict)
def add_items(
    object_id: int,
    act_id: int,
    body: ActItemsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> dict:
    act = _get_act_or_404(act_id, db, obj)
    found = set(
        db.scalars(
            select(SourceItem.id).where(
                SourceItem.object_id == obj.id, SourceItem.id.in_(set(body.item_ids))
            )
        )
    )
    for item_id in found:
        exists = db.scalar(
            select(act_item.c.source_item_id).where(
                act_item.c.act_id == act.id, act_item.c.source_item_id == item_id
            )
        )
        if not exists:
            db.execute(insert(act_item).values(act_id=act.id, source_item_id=item_id))
    db.commit()
    return {"linked_items": _linked(act.id, db)}


@router.post("/{act_id}/items/remove", response_model=dict)
def remove_items(
    object_id: int,
    act_id: int,
    body: ActItemsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> dict:
    act = _get_act_or_404(act_id, db, obj)
    if body.item_ids:
        db.execute(
            sa_delete(act_item).where(
                act_item.c.act_id == act.id,
                act_item.c.source_item_id.in_(body.item_ids),
            )
        )
        db.commit()
    return {"linked_items": _linked(act.id, db)}


@router.delete("/{act_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_act(
    object_id: int,
    act_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> None:
    act = _get_act_or_404(act_id, db, obj)
    db.execute(sa_delete(act_item).where(act_item.c.act_id == act.id))
    db.delete(act)
    db.commit()


def _build_docx(act: Act, items: list[SourceItem]) -> bytes:
    from docx import Document

    doc = Document()
    title = ACT_TYPE_LABELS.get(act.act_type, str(act.act_type))
    doc.add_heading(f"{title} № {act.doc_number or ''}", level=1)
    doc.add_paragraph(f"Дата: {act.doc_date or '—'}")
    doc.add_paragraph("Позиции:")

    table = doc.add_table(rows=1, cols=7)
    table.style = "Light Grid Accent 1"
    header = table.rows[0].cells
    for i, text in enumerate(["Шифр", "Поз.", "Наименование", "Марка", "Ед.", "Кол.", "Паспорт"]):
        header[i].text = text
    for it in items:
        cells = table.add_row().cells
        cells[0].text = it.full_code or ""
        cells[1].text = it.position or ""
        cells[2].text = it.name
        cells[3].text = it.mark or ""
        cells[4].text = it.unit or ""
        cells[5].text = str(it.quantity or "")
        cells[6].text = str(len(it.docs))
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


@router.get("/{act_id}/generate")
def generate_docx(
    object_id: int,
    act_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
):
    from fastapi.responses import StreamingResponse

    act = _get_act_or_404(act_id, db, obj)
    items = list(
        db.scalars(
            select(SourceItem)
            .options(selectinload(SourceItem.docs))
            .join(act_item, act_item.c.source_item_id == SourceItem.id)
            .where(act_item.c.act_id == act.id)
            .order_by(SourceItem.row_number)
        )
    )
    data = _build_docx(act, items)
    filename = f"act_{act.act_type.value}_{act.id}.docx"
    headers = {"Content-Disposition": f'attachment; filename="{Path(filename).name}"'}
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
