"""Перечисления предметной области."""

from enum import Enum


class UserRole(str, Enum):
    """Роли пользователей. Админ = суперпользователь своей компании."""

    ADMIN = "admin"
    PTO_HEAD = "pto_head"  # Руководитель ПТО
    PTO_ENGINEER = "pto_engineer"  # Инженер ПТО


class ObjectStatus(str, Enum):
    PLANNING = "planning"  # Планируется
    ACTIVE = "active"  # В работе
    CLOSED = "closed"  # Закрыт
