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


class DocKind(str, Enum):
    """Вид документа при загрузке на объект."""

    SPECIFICATION = "spec"  # спецификация из РД
    ESTIMATE = "estimate"  # смета
    PASSPORT = "passport"  # паспорта/сертификаты
    OTHER = "other"


class ParseStatus(str, Enum):
    UPLOADED = "uploaded"  # только загружен
    PARSING = "parsing"  # идёт разбор
    DONE = "done"  # разобран
    ERROR = "error"  # ошибка разбора


class ItemSource(str, Enum):
    """Происхождение позиции."""

    RD = "rd"  # рабочая документация (спецификация)
    ESTIMATE = "estimate"  # смета


class ActType(str, Enum):
    """Типы актов (закрывающие документы)."""

    AVK = "avk"  # акт входного контроля (материалы/оборудование)
    AOSR = "aosr"  # акт освидетельствования скрытых работ
    VSO = "vso"  # ведомость смонтированного оборудования
    VR = "vr"  # ведомость выполненных работ


class ActStatus(str, Enum):
    DRAFT = "draft"  # черновик (для печати)
    READY = "ready"  # подписан/готов
