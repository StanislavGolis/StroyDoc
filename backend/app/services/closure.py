"""Матрица закрытия позиций: какие документы требуются для каждого типа позиции.

Правило заказчика (10.09.2026):

- материал     — паспорт/сертификат, АВК, АОСР;
- оборудование — паспорт/сертификат, АВК, ВСО;
- работа       — только ВР.

Тип позиции может быть не определён (``None``) — тогда требования ограничиваются
паспортом и АВК: пока не подтверждено, что строка из «Ведомости объёмов работ»,
документы считаются нужными (консервативно, риск не скрывается).

Модуль — единый источник истины для API, дашборда и UI (через поле ``required_docs``).
"""

from __future__ import annotations

from app.models.enums import ActType, ItemType

PASSPORT = "passport"

#: Ключи закрывающих документов по типам позиций.
REQUIRED_DOCS: dict[ItemType, tuple[str, ...]] = {
    ItemType.MATERIAL: (PASSPORT, ActType.AVK.value, ActType.AOSR.value),
    ItemType.EQUIPMENT: (PASSPORT, ActType.AVK.value, ActType.VSO.value),
    ItemType.WORK: (ActType.VR.value,),
}

#: Требования для позиций с неопределённым типом.
UNTYPED_REQUIRED_DOCS: tuple[str, ...] = (PASSPORT, ActType.AVK.value)

#: Типы позиций, которые закрывает акт данного вида.
ACT_COVERS: dict[ActType, tuple[str, ...]] = {
    ActType.AVK: (ItemType.MATERIAL.value, ItemType.EQUIPMENT.value),
    ActType.AOSR: (ItemType.MATERIAL.value,),
    ActType.VSO: (ItemType.EQUIPMENT.value,),
    ActType.VR: (ItemType.WORK.value,),
}

#: Допускает ли акт позиции с неопределённым типом.
#: Для ВР нет: это ведомость работ, туда попадают только распознанные работы.
ACT_ALLOWS_UNTYPED: dict[ActType, bool] = {
    ActType.AVK: True,
    ActType.AOSR: True,
    ActType.VSO: True,
    ActType.VR: False,
}

#: Ключ «паспорт/сертификат» не является актом — он хранится отдельно.
ACT_KEYS: tuple[str, ...] = tuple(at.value for at in ActType)


def normalize_item_type(value: object) -> ItemType | None:
    """Приводит значение типа позиции к :class:`ItemType` (``None`` — не определён)."""
    if value is None or value == "":
        return None
    if isinstance(value, ItemType):
        return value
    return ItemType(str(value))


def normalize_act_type(value: object) -> ActType:
    """Приводит значение типа акта к :class:`ActType`."""
    if isinstance(value, ActType):
        return value
    return ActType(str(value))


def required_docs(item_type: object) -> list[str]:
    """Ключи документов, требуемых для позиции (для колонок UI/статусов)."""
    t = normalize_item_type(item_type)
    if t is None:
        return list(UNTYPED_REQUIRED_DOCS)
    return list(REQUIRED_DOCS[t])


def act_covers(act_type: object, item_type: object) -> bool:
    """Может ли акт данного вида закрывать позицию данного типа."""
    at = normalize_act_type(act_type)
    t = normalize_item_type(item_type)
    if t is None:
        return ACT_ALLOWS_UNTYPED[at]
    return t.value in ACT_COVERS[at]


def act_covers_types(act_type: object) -> tuple[tuple[str, ...], bool]:
    """(явные типы позиций, допускается ли неопределённый тип) — для SQL-фильтров."""
    at = normalize_act_type(act_type)
    return ACT_COVERS[at], ACT_ALLOWS_UNTYPED[at]
