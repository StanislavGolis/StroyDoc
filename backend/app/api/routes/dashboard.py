"""Дашборд руководителя: сводка по всем объектам компании.

Счётчики закрытия считаются по матрице из :mod:`app.services.closure`:
АВК — материалы + оборудование, АОСР — материалы, ВСО — оборудование, ВР — работы.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_manager
from app.db.session import get_db
from app.models import (
    Act,
    ConstructionObject,
    IncomingDoc,
    SourceItem,
    User,
    act_item,
    incoming_doc_item,
)
from app.models.enums import ActType, ItemType, ObjectStatus
from app.schemas.dashboard import DashboardSummary, DashboardTotals, ObjectDashItem
from app.services.closure import act_covers

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

WORK = ItemType.WORK.value
MATERIAL = ItemType.MATERIAL.value
EQUIPMENT = ItemType.EQUIPMENT.value

#: Позиции, для которых требуется паспорт/сертификат (всё, что не работа).
_PASSPORT_REQUIRED = or_(SourceItem.item_type.is_(None), SourceItem.item_type != WORK)


def _tracked_by_type(db: Session, object_id: int) -> dict[str | None, int]:
    """Отслеживаемые позиции объекта в разбивке по типу (None — тип не определён)."""
    rows = db.execute(
        select(SourceItem.item_type, func.count())
        .where(SourceItem.object_id == object_id, SourceItem.tracked.is_(True))
        .group_by(SourceItem.item_type)
    ).all()
    return {row[0]: row[1] for row in rows}


def _closed_by_act_and_type(db: Session, object_id: int) -> dict[tuple[str, str | None], int]:
    """Сколько отслеживаемых позиций объекта закрыто актами, по (вид акта, тип позиции)."""
    rows = db.execute(
        select(
            Act.act_type,
            SourceItem.item_type,
            func.count(func.distinct(act_item.c.source_item_id)),
        )
        .join(Act, Act.id == act_item.c.act_id)
        .join(SourceItem, SourceItem.id == act_item.c.source_item_id)
        .where(Act.object_id == object_id, SourceItem.tracked.is_(True))
        .group_by(Act.act_type, SourceItem.item_type)
    ).all()
    result: dict[tuple[str, str | None], int] = {}
    for act_type, item_type, cnt in rows:
        key = act_type.value if isinstance(act_type, ActType) else str(act_type)
        result[(key, item_type)] = cnt
    return result


def _closed_total(closed: dict[tuple[str, str | None], int], act_type: ActType) -> int:
    """Позиции, закрытые актом вида act_type, с учётом допустимых типов позиций."""
    return sum(
        cnt
        for (closed_act, item_type), cnt in closed.items()
        if closed_act == act_type.value and act_covers(act_type, item_type)
    )


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), manager: User = Depends(require_manager)) -> DashboardSummary:
    objs = list(
        db.scalars(
            select(ConstructionObject)
            .where(ConstructionObject.company_id == manager.company_id)
            .order_by(ConstructionObject.created_at.desc())
        )
    )
    objects: list[ObjectDashItem] = []
    totals_tracked = totals_with = totals_passport_required = 0
    acts_by_type: dict[str, int] = {"avk": 0, "aosr": 0, "vso": 0, "vr": 0}
    acts_total = passports_total = 0

    for o in objs:
        by_type = _tracked_by_type(db, o.id)
        material = by_type.get(MATERIAL, 0)
        equipment = by_type.get(EQUIPMENT, 0)
        work = by_type.get(WORK, 0)
        untyped = by_type.get(None, 0)
        tracked = material + equipment + work + untyped
        # паспорт/сертификат нужен всему, что не работа
        passport_required = material + equipment + untyped
        with_docs = db.scalar(
            select(func.count(func.distinct(incoming_doc_item.c.source_item_id)))
            .join(SourceItem, SourceItem.id == incoming_doc_item.c.source_item_id)
            .where(
                SourceItem.object_id == o.id,
                SourceItem.tracked.is_(True),
                _PASSPORT_REQUIRED,
            )
        ) or 0
        act_count = db.scalar(
            select(func.count()).select_from(Act).where(Act.object_id == o.id)
        ) or 0
        closed = _closed_by_act_and_type(db, o.id)
        ready = round(with_docs / passport_required * 100) if passport_required else 0
        objects.append(
            ObjectDashItem(
                object_id=o.id,
                name=o.name,
                code=o.code,
                status=o.status,
                tracked_items=tracked,
                items_with_docs=with_docs,
                items_without_docs=max(passport_required - with_docs, 0),
                ready_pct=ready,
                acts_total=act_count,
                work_total=work,
                vr_closed=_closed_total(closed, ActType.VR),
                non_work_total=passport_required,
                avk_closed=_closed_total(closed, ActType.AVK),
                aosr_closed=_closed_total(closed, ActType.AOSR),
                vso_closed=_closed_total(closed, ActType.VSO),
                material_total=material,
                equipment_total=equipment,
                untyped_total=untyped,
            )
        )
        totals_tracked += tracked
        totals_with += with_docs
        totals_passport_required += passport_required

    for act_type, cnt in db.execute(
        select(Act.act_type, func.count()).where(Act.company_id == manager.company_id).group_by(Act.act_type)
    ):
        acts_by_type[act_type.value] = cnt
        acts_total += cnt

    passports_total = db.scalar(
        select(func.count())
        .select_from(IncomingDoc)
        .where(IncomingDoc.company_id == manager.company_id)
    ) or 0

    active_count = sum(1 for o in objs if o.status == ObjectStatus.ACTIVE)
    return DashboardSummary(
        objects=objects,
        totals=DashboardTotals(
            objects_total=len(objs),
            objects_active=active_count,
            tracked_items=totals_tracked,
            items_with_docs=totals_with,
            items_without_docs=max(totals_passport_required - totals_with, 0),
            ready_pct=(
                round(totals_with / totals_passport_required * 100)
                if totals_passport_required
                else 0
            ),
            acts_total=acts_total,
            acts_by_type=acts_by_type,
            passports=passports_total,
        ),
    )
