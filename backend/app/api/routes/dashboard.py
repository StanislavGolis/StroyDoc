"""Дашборд руководителя: сводка по всем объектам компании."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_manager
from app.db.session import get_db
from app.models import Act, ConstructionObject, IncomingDoc, SourceItem, User, incoming_doc_item
from app.models.enums import ObjectStatus
from app.schemas.dashboard import DashboardSummary, DashboardTotals, ObjectDashItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


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
    totals_tracked = totals_with = 0
    acts_by_type: dict[str, int] = {"avk": 0, "aosr": 0, "vso": 0, "vr": 0}
    acts_total = passports_total = 0

    for o in objs:
        tracked = db.scalar(
            select(func.count())
            .select_from(SourceItem)
            .where(SourceItem.object_id == o.id, SourceItem.tracked.is_(True))
        ) or 0
        with_docs = db.scalar(
            select(func.count(func.distinct(incoming_doc_item.c.source_item_id)))
            .join(SourceItem, SourceItem.id == incoming_doc_item.c.source_item_id)
            .where(SourceItem.object_id == o.id, SourceItem.tracked.is_(True))
        ) or 0
        act_count = db.scalar(
            select(func.count()).select_from(Act).where(Act.object_id == o.id)
        ) or 0
        ready = round(with_docs / tracked * 100) if tracked else 0
        objects.append(
            ObjectDashItem(
                object_id=o.id,
                name=o.name,
                code=o.code,
                status=o.status,
                tracked_items=tracked,
                items_with_docs=with_docs,
                items_without_docs=tracked - with_docs,
                ready_pct=ready,
                acts_total=act_count,
            )
        )
        totals_tracked += tracked
        totals_with += with_docs

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
            items_without_docs=totals_tracked - totals_with,
            ready_pct=round(totals_with / totals_tracked * 100) if totals_tracked else 0,
            acts_total=acts_total,
            acts_by_type=acts_by_type,
            passports=passports_total,
        ),
    )
