from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import ItemSource
from app.schemas.sections import SectionBrief


class TrackedBulkRequest(BaseModel):
    """Массовое включение/выключение отслеживания позиций."""

    tracked: bool
    section_id: int | None = None
    ids: list[int] | None = None


class SourceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    source_file_id: int | None
    source: ItemSource
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
