from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import ItemSource
from app.schemas.sections import SectionBrief


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
    created_at: datetime
