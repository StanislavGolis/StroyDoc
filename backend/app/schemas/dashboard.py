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
    # работы (из «Ведомостей объемов работ») и их закрытие ВР
    work_total: int
    vr_closed: int
    # остальные позиции (материалы + оборудование + не типизированные) и закрытие по типам
    non_work_total: int
    avk_closed: int
    aosr_closed: int
    vso_closed: int
    # разбивка не-работ по типам позиции (матрица закрытия, см. app.services.closure)
    material_total: int
    equipment_total: int
    #: позиции, тип которых не определён — требуется ручная классификация
    untyped_total: int


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
