"""ORM-модели. Импорт сюда гарантирует регистрацию всех таблиц в Base.metadata."""
from app.models.assignment import ObjectAssignment
from app.models.company import Company
from app.models.construction_object import ConstructionObject
from app.models.object_file import ObjectFile
from app.models.rd_section import RdSection
from app.models.source_item import SourceItem
from app.models.user import User

__all__ = [
    "Company",
    "User",
    "ConstructionObject",
    "ObjectAssignment",
    "RdSection",
    "ObjectFile",
    "SourceItem",
]
