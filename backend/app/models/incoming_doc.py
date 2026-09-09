from datetime import datetime

from sqlalchemy import Column, Date, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

# Связь «паспорт/сертификат ↔ позиция» (многие-ко-многим): один документ (партия) может
# закрывать несколько позиций, у позиции может быть несколько документов.
incoming_doc_item = Table(
    "incoming_doc_item",
    Base.metadata,
    Column(
        "incoming_doc_id",
        ForeignKey("incoming_doc.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "source_item_id",
        ForeignKey("source_item.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class IncomingDoc(Base):
    """Паспорт/сертификат в библиотеке документов объекта."""

    __tablename__ = "incoming_doc"
    __table_args__ = (UniqueConstraint("object_id", "file_id", name="uq_incoming_doc_object_file"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"), index=True)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("construction_object.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[int | None] = mapped_column(
        ForeignKey("object_file.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    doc_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    doc_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    doc_date = mapped_column(Date, nullable=True)  # дата документа
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)

    file: Mapped["ObjectFile | None"] = relationship(back_populates="doc")  # noqa: F821
    items: Mapped[list["SourceItem"]] = relationship(  # noqa: F821
        secondary=incoming_doc_item, back_populates="docs"
    )
