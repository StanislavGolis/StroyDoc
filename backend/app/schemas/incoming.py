from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class IncomingDocRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    doc_number: str | None
    doc_title: str | None
    doc_date: date | None
    file_id: int | None
    original_filename: str | None
    size_bytes: int | None
    linked_items: int
    created_at: datetime


class IncomingDocUpdate(BaseModel):
    doc_number: str | None = None
    doc_title: str | None = None
    doc_date: date | None = None


class DocAttachRequest(BaseModel):
    item_ids: list[int]
