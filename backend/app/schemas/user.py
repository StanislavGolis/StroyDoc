from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole


class UserCreateRequest(UserBase):
    """Создание пользователя менеджером. Пароль генерирует сервер."""


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    is_active: bool
    created_at: datetime


class UserCreatedResponse(BaseModel):
    """Ответ с одноразово показанным сгенерированным паролем."""

    user: UserRead
    generated_password: str


class UserResetPasswordResponse(BaseModel):
    user: UserRead
    generated_password: str
