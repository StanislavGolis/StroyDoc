from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "user"
    __table_args__ = (UniqueConstraint("company_id", "email", name="uq_user_company_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(nullable=False, default=UserRole.PTO_ENGINEER)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Версия токена: инкремент инвалидирует все refresh-токены пользователя (logout, сброс пароля)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow, onupdate=utcnow)

    company: Mapped["Company"] = relationship(back_populates="users")  # noqa: F821
    assignments: Mapped[list["ObjectAssignment"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan", foreign_keys="ObjectAssignment.user_id"
    )

    @property
    def is_manager(self) -> bool:
        """Руководитель ПТО или администратор управляют объектами и пользователями."""
        return self.role in (UserRole.ADMIN, UserRole.PTO_HEAD)
