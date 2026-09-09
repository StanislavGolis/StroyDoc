from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocKind, ParseStatus
from app.schemas.sections import SectionBrief


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    kind: DocKind
    section: SectionBrief | None
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    status: ParseStatus
    error_message: str | None
    parsed_items: int
    created_at: datetime
    uploader: UserBrief | None


class FileSectionUpdate(BaseModel):
    """Перенос файла в другой шифр (или отвязка, section_id=None)."""

    section_id: int | None = None
