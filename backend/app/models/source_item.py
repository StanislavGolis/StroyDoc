from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import ItemSource


class SourceItem(Base):
    """Сырая позиция, извлечённая из источника (РД-спецификация / смета).

    На этом уровне хранится «как в документе». Сведение в Мастер-список —
    задача Спринта 3 (конфликт-детектор).
    """

    __tablename__ = "source_item"
    __table_args__ = (
        UniqueConstraint("source_file_id", "row_number", name="uq_source_item_file_row"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("construction_object.id", ondelete="CASCADE"), index=True
    )
    source_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("object_file.id", ondelete="CASCADE"), nullable=True
    )
    source: Mapped[ItemSource] = mapped_column(nullable=False, default=ItemSource.RD)
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("rd_section.id", ondelete="SET NULL"), nullable=True, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Поля из документа (по возможности структурированы).
    # Тип Text: это «сырые» значения из PDF, они могут содержать мусор от вёрстки.
    position: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Поз.
    name: Mapped[str] = mapped_column(Text, nullable=False)  # Наименование и тех. характеристика
    mark: Mapped[str | None] = mapped_column(Text, nullable=True)  # Тип, марка
    doc_ref: Mapped[str | None] = mapped_column(Text, nullable=True)  # ГОСТ / ТУ / обозначение документа
    product_code: Mapped[str | None] = mapped_column(Text, nullable=True)  # Код продукции
    supplier: Mapped[str | None] = mapped_column(Text, nullable=True)  # Поставщик
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)  # Ед. измерения
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)  # Кол.
    mass: Mapped[str | None] = mapped_column(Text, nullable=True)  # Масса 1 ед. (как в документе)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # Примечания
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)

    source_file: Mapped["ObjectFile"] = relationship(back_populates="items")  # noqa: F821
    section: Mapped["RdSection | None"] = relationship(foreign_keys=[section_id])  # noqa: F821
