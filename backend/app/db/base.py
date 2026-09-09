from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """Наивное UTC-время для хранения в БД."""
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass
