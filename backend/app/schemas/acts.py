from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ActStatus, ActType


class ActRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    act_type: ActType
    doc_number: str | None
    doc_date: date | None
    status: ActStatus
    linked_items: int
    created_at: datetime


class ActCreate(BaseModel):
    act_type: ActType
    doc_number: str | None = None
    doc_date: date | None = None
    item_ids: list[int] = []


class ActUpdate(BaseModel):
    doc_number: str | None = None
    doc_date: date | None = None
    status: ActStatus | None = None


class ActItemsRequest(BaseModel):
    item_ids: list[int]
