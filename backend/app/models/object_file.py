from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import DocKind, ParseStatus


class ObjectFile(Base):
    """Файл, загруженный на объект (спецификации, сметы, паспорта). Хранится в S3/local."""

    __tablename__ = "object_file"
    __table_args__ = (
        UniqueConstraint("object_id", "sha256", name="uq_object_file_object_sha256"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"), index=True)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("construction_object.id", ondelete="CASCADE"), index=True
    )
    uploader_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[DocKind] = mapped_column(nullable=False, default=DocKind.OTHER)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(200), nullable=False, default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(700), nullable=False, unique=True)
    status: Mapped[ParseStatus] = mapped_column(nullable=False, default=ParseStatus.UPLOADED)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    parsed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)

    object: Mapped["ConstructionObject"] = relationship(back_populates="files")  # noqa: F821
    uploader: Mapped["User | None"] = relationship(foreign_keys=[uploader_id])  # noqa: F821
    items: Mapped[list["SourceItem"]] = relationship(  # noqa: F821
        back_populates="source_file", cascade="all, delete-orphan"
    )
