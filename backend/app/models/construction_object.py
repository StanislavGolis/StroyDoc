from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import ObjectStatus


class ConstructionObject(Base):
    """Объект строительства, с которым работает отдел ПТО."""

    __tablename__ = "construction_object"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100), nullable=True)  # шифр объекта
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[ObjectStatus] = mapped_column(nullable=False, default=ObjectStatus.PLANNING)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow, onupdate=utcnow)

    company: Mapped["Company"] = relationship(back_populates="objects")  # noqa: F821
    assignments: Mapped[list["ObjectAssignment"]] = relationship(  # noqa: F821
        back_populates="object", cascade="all, delete-orphan"
    )
