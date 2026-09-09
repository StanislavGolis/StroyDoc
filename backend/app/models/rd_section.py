from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class RdSection(Base):
    """Шифр рабочей документации внутри объекта (ТСО, КЖ, ЭМ, узел 7-ТСО, ...).

    Рабочая область объекта состоит из разделов-шифров; их число не ограничено.
    """

    __tablename__ = "rd_section"
    __table_args__ = (UniqueConstraint("object_id", "code", name="uq_rd_section_object_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"), index=True)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("construction_object.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)  # короткое обозначение шифра
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # расшифровка (необязательна)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Полный шифр листа спецификации (напр. «00819.РП.0.000.0-ТСО.СО1») и категория поставки
    full_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)

    object: Mapped["ConstructionObject"] = relationship(back_populates="sections")  # noqa: F821
    files: Mapped[list["ObjectFile"]] = relationship(back_populates="section")  # noqa: F821
