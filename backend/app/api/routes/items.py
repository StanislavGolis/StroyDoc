"""Позиции, извлечённые из загруженных документов (РД-спецификации, сметы)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_object_access
from app.db.session import get_db
from app.models import ConstructionObject, SourceItem, User, incoming_doc_item
from app.models.enums import ItemSource
from app.schemas.items import SourceItemRead, SourceItemUpdate, TrackedBulkRequest

router = APIRouter(prefix="/objects/{object_id}/items", tags=["items"])


@router.get("", response_model=list[SourceItemRead])
def list_items(
    object_id: int,
    source: ItemSource | None = Query(default=None),
    source_file: int | None = Query(default=None),
    section: int | None = Query(default=None),
    tracked: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> list[SourceItem]:
    stmt = select(SourceItem).options(selectinload(SourceItem.section)).where(
        SourceItem.object_id == obj.id
    )
    if source is not None:
        stmt = stmt.where(SourceItem.source == source)
    if source_file is not None:
        stmt = stmt.where(SourceItem.source_file_id == source_file)
    if section is not None:
        stmt = stmt.where(SourceItem.section_id == section)
    if tracked is not None:
        stmt = stmt.where(SourceItem.tracked == tracked)
    stmt = stmt.order_by(SourceItem.section_id, SourceItem.row_number)
    rows = list(db.scalars(stmt))
    counts: dict[int, int] = {}
    if rows:
        ids = [r.id for r in rows]
        for item_id, cnt in db.execute(
            select(
                incoming_doc_item.c.source_item_id, func.count(incoming_doc_item.c.incoming_doc_id)
            )
            .where(incoming_doc_item.c.source_item_id.in_(ids))
            .group_by(incoming_doc_item.c.source_item_id)
        ):
            counts[item_id] = cnt
    return [
        SourceItemRead.model_validate(it).model_copy(update={"docs_count": counts.get(it.id, 0)})
        for it in rows
    ]


@router.post("/set-tracked", response_model=dict)
def set_tracked(
    object_id: int,
    body: TrackedBulkRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> dict:
    """Включить/выключить отслеживание для набора позиций (по объекту/шифру/списку id)."""
    from sqlalchemy import update

    stmt = update(SourceItem).where(SourceItem.object_id == obj.id)
    if body.section_id is not None:
        stmt = stmt.where(SourceItem.section_id == body.section_id)
    if body.ids is not None:
        stmt = stmt.where(SourceItem.id.in_(body.ids))
    stmt = stmt.values(tracked=body.tracked)
    result = db.execute(stmt)
    db.commit()
    return {"updated": result.rowcount}


@router.patch("/{item_id}", response_model=SourceItemRead)
def update_item(
    object_id: int,
    item_id: int,
    body: SourceItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> SourceItem:
    """Инженер правит поля позиции и признак отслеживания."""
    item = db.get(SourceItem, item_id)
    if item is None or item.object_id != obj.id:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    for field in (
        "position",
        "name",
        "mark",
        "doc_ref",
        "product_code",
        "supplier",
        "unit",
        "quantity",
        "mass",
        "notes",
        "full_code",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(item, field, value)
    if body.tracked is not None:
        item.tracked = body.tracked
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
