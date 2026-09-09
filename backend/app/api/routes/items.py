"""Позиции, извлечённые из загруженных документов (РД-спецификации, сметы)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_object_access
from app.db.session import get_db
from app.models import Act, ConstructionObject, SourceItem, User, act_item, incoming_doc_item
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
    act_counts: dict[tuple[int, str], int] = {}
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
        for item_id, act_type, cnt in db.execute(
            select(act_item.c.source_item_id, Act.act_type, func.count())
            .join(Act, Act.id == act_item.c.act_id)
            .where(act_item.c.source_item_id.in_(ids))
            .group_by(act_item.c.source_item_id, Act.act_type)
        ):
            act_counts[(item_id, act_type.value)] = cnt
    result = []
    for it in rows:
        item = SourceItemRead.model_validate(it).model_copy(
            update={
                "docs_count": counts.get(it.id, 0),
                "act_avk": act_counts.get((it.id, "avk"), 0),
                "act_aosr": act_counts.get((it.id, "aosr"), 0),
                "act_vso": act_counts.get((it.id, "vso"), 0),
                "act_vr": act_counts.get((it.id, "vr"), 0),
            }
        )
        result.append(item)
    return result


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
    """Инженер правит поля позиции и признак отслеживания.

    Применяются только явно переданные поля — так можно и очищать (null),
    и не затирать остальные.
    """
    item = db.get(SourceItem, item_id)
    if item is None or item.object_id != obj.id:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    updates = body.model_dump(exclude_unset=True)
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
        "tracked",
    ):
        if field in updates:
            setattr(item, field, updates[field])
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
