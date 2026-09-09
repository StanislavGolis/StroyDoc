from datetime import datetime

from sqlalchemy import Column, Date, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import ActStatus, ActType

# Позиции, включённые в акт
act_item = Table(
    "act_item",
    Base.metadata,
    Column("act_id", ForeignKey("act.id", ondelete="CASCADE"), primary_key=True),
    Column("source_item_id", ForeignKey("source_item.id", ondelete="CASCADE"), primary_key=True),
)


class Act(Base):
    """Акт (черновик для печати): АВК / АОСР / ВСО / ВР."""

    __tablename__ = "act"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"), index=True)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("construction_object.id", ondelete="CASCADE"), index=True
    )
    act_type: Mapped[ActType] = mapped_column(nullable=False, default=ActType.AVK)
    doc_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    doc_date = mapped_column(Date, nullable=True)
    status: Mapped[ActStatus] = mapped_column(nullable=False, default=ActStatus.DRAFT)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)

    items: Mapped[list["SourceItem"]] = relationship(  # noqa: F821
        secondary=act_item, back_populates="acts"
    )
