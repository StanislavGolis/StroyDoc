from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class Company(Base):
    """Компания-владелец данных. Фундамент мультитенантности (company_id)."""

    __tablename__ = "company"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="company")  # noqa: F821
    objects: Mapped[list["ConstructionObject"]] = relationship(back_populates="company")  # noqa: F821
