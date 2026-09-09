"""ORM-модели. Импорт сюда гарантирует регистрацию всех таблиц в Base.metadata."""
from app.models.assignment import ObjectAssignment
from app.models.company import Company
from app.models.construction_object import ConstructionObject
from app.models.user import User

__all__ = [
    "Company",
    "User",
    "ConstructionObject",
    "ObjectAssignment",
]
