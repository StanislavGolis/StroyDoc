from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class ObjectAssignment(Base):
    """Назначение инженера ПТО на объект строительства."""

    __tablename__ = "object_assignment"
    __table_args__ = (UniqueConstraint("object_id", "user_id", name="uq_assignment_object_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("construction_object.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)

    object: Mapped["ConstructionObject"] = relationship(back_populates="assignments")  # noqa: F821
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="assignments", foreign_keys=[user_id]
    )
