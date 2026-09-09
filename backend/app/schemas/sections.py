from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SectionBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str | None


class SectionCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=255)
    sort_order: int = 0


class SectionUpdateRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=255)
    sort_order: int | None = None


class SectionRead(SectionBrief):
    object_id: int
    sort_order: int
    created_at: datetime
