"""Позиции, извлечённые из загруженных документов (РД-спецификации, сметы)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_object_access
from app.db.session import get_db
from app.models import Act, ConstructionObject, SourceItem, User, act_item, incoming_doc_item
from app.models.enums import ItemSource, ItemType
from app.schemas.items import (
    ItemTypeBulkRequest,
    SourceItemRead,
    SourceItemUpdate,
    TrackedBulkRequest,
)
from app.services.closure import required_docs

router = APIRouter(prefix="/objects/{object_id}/items", tags=["items"])


@router.get("", response_model=list[SourceItemRead])
def list_items(
    object_id: int,
    source: ItemSource | None = Query(default=None),
    source_file: int | None = Query(default=None),
    section: int | None = Query(default=None),
    tracked: bool | None = Query(default=None),
    item_type: ItemType | None = Query(default=None),
    untyped: bool | None = Query(default=None),
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
    if item_type is not None:
        stmt = stmt.where(SourceItem.item_type == item_type.value)
    if untyped is not None:
        # untyped=true — только позиции без определённого типа (item_type IS NULL)
        stmt = stmt.where(
            SourceItem.item_type.is_(None) if untyped else SourceItem.item_type.is_not(None)
        )
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
                "required_docs": required_docs(it.item_type),
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


@router.post("/set-type", response_model=dict)
def set_type(
    object_id: int,
    body: ItemTypeBulkRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> dict:
    """Массово присвоить (или сбросить) тип позиции.

    Область применения: по объекту/шифру/списку id; ``only_untyped=true`` —
    только позиции без определённого типа (удобно для «разбора» после парсинга).
    """
    from sqlalchemy import update

    stmt = update(SourceItem).where(SourceItem.object_id == obj.id)
    if body.section_id is not None:
        stmt = stmt.where(SourceItem.section_id == body.section_id)
    if body.ids is not None:
        stmt = stmt.where(SourceItem.id.in_(body.ids))
    if body.only_untyped:
        stmt = stmt.where(SourceItem.item_type.is_(None))
    stmt = stmt.values(item_type=body.item_type.value if body.item_type else None)
    result = db.execute(stmt)
    db.commit()
    return {"updated": result.rowcount}


def _enrich(db: Session, item: SourceItem) -> dict:
    """Вычисляемые поля позиции: документы, акты по видам, требования матрицы."""
    docs_count = db.scalar(
        select(func.count())
        .select_from(incoming_doc_item)
        .where(incoming_doc_item.c.source_item_id == item.id)
    ) or 0
    acts: dict[str, int] = {"avk": 0, "aosr": 0, "vso": 0, "vr": 0}
    for act_type, cnt in db.execute(
        select(Act.act_type, func.count())
        .join(act_item, act_item.c.act_id == Act.id)
        .where(act_item.c.source_item_id == item.id)
        .group_by(Act.act_type)
    ):
        key = act_type.value if hasattr(act_type, "value") else str(act_type)
        acts[key] = cnt
    return {
        "docs_count": docs_count,
        "act_avk": acts["avk"],
        "act_aosr": acts["aosr"],
        "act_vso": acts["vso"],
        "act_vr": acts["vr"],
        "required_docs": required_docs(item.item_type),
    }


@router.patch("/{item_id}", response_model=SourceItemRead)
def update_item(
    object_id: int,
    item_id: int,
    body: SourceItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> SourceItemRead:
    """Инженер правит поля позиции и признак отслеживания.

    Применяются только явно переданные поля — так можно и очищать (null),
    и не затирать остальные.
    """
    item = db.get(SourceItem, item_id)
    if item is None or item.object_id != obj.id:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    updates = body.model_dump(exclude_unset=True)
    # тип позиции: enum -> строка; None означает «сбросить тип»
    if "item_type" in updates:
        new_type = updates.pop("item_type")
        item.item_type = new_type.value if isinstance(new_type, ItemType) else new_type
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
    return SourceItemRead.model_validate(item).model_copy(update=_enrich(db, item))
