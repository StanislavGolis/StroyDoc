from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import ItemSource, ItemType
from app.schemas.sections import SectionBrief


class TrackedBulkRequest(BaseModel):
    """Массовое включение/выключение отслеживания позиций."""

    tracked: bool
    section_id: int | None = None
    ids: list[int] | None = None


class ItemTypeBulkRequest(BaseModel):
    """Массовое присвоение типа позиции (по объекту/шифру/списку id/только не типизированным)."""

    item_type: ItemType | None = None  # None — сбросить тип
    section_id: int | None = None
    ids: list[int] | None = None
    only_untyped: bool = False


class SourceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    source_file_id: int | None
    source: ItemSource
    item_type: str | None
    #: Ключи документов, требуемых для этой позиции (матрица закрытия) — см. app.services.closure
    required_docs: list[str] = []
    section: SectionBrief | None
    row_number: int
    position: str | None
    name: str
    mark: str | None
    doc_ref: str | None
    product_code: str | None
    supplier: str | None
    unit: str | None
    quantity: Decimal | None
    mass: str | None
    notes: str | None
    full_code: str | None
    page_number: int | None
    tracked: bool
    docs_count: int = 0
    act_avk: int = 0
    act_aosr: int = 0
    act_vso: int = 0
    act_vr: int = 0
    created_at: datetime


class SourceItemUpdate(BaseModel):
    """Инженер правит позицию «как в документе» и управляет признаком отслеживания."""

    position: str | None = None
    name: str | None = None
    mark: str | None = None
    doc_ref: str | None = None
    product_code: str | None = None
    supplier: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    mass: str | None = None
    notes: str | None = None
    full_code: str | None = None
    tracked: bool | None = None
    item_type: ItemType | None = None
