from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ObjectStatus


class ObjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    code: str | None = Field(default=None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    status: ObjectStatus = ObjectStatus.PLANNING


class ObjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    code: str | None = Field(default=None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    status: ObjectStatus | None = None


class ObjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str
    code: str | None
    start_date: date | None
    end_date: date | None
    status: ObjectStatus
    created_at: datetime


class AssignmentCreateRequest(BaseModel):
    user_id: int


class AssignmentUserRead(BaseModel):
    """Компактная информация о назначенном пользователе."""

    id: int
    full_name: str
    email: str
    role: str


class AssignmentRead(BaseModel):
    id: int
    object_id: int
    user: AssignmentUserRead
    created_at: datetime
