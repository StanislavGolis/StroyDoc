from pydantic import BaseModel


class ObjectDashItem(BaseModel):
    object_id: int
    name: str
    code: str | None
    status: str
    tracked_items: int
    items_with_docs: int
    items_without_docs: int
    ready_pct: int
    acts_total: int


class DashboardTotals(BaseModel):
    objects_total: int
    objects_active: int
    tracked_items: int
    items_with_docs: int
    items_without_docs: int
    ready_pct: int
    acts_total: int
    acts_by_type: dict[str, int]
    passports: int


class DashboardSummary(BaseModel):
    objects: list[ObjectDashItem]
    totals: DashboardTotals
