"""Позиции, извлечённые из загруженных документов (РД-спецификации, сметы)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_object_access
from app.db.session import get_db
from app.models import ConstructionObject, SourceItem, User
from app.models.enums import ItemSource
from app.schemas.items import SourceItemRead

router = APIRouter(prefix="/objects/{object_id}/items", tags=["items"])


@router.get("", response_model=list[SourceItemRead])
def list_items(
    object_id: int,
    source: ItemSource | None = Query(default=None),
    source_file: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> list[SourceItem]:
    stmt = select(SourceItem).where(SourceItem.object_id == obj.id)
    if source is not None:
        stmt = stmt.where(SourceItem.source == source)
    if source_file is not None:
        stmt = stmt.where(SourceItem.source_file_id == source_file)
    stmt = stmt.order_by(SourceItem.row_number)
    return list(db.scalars(stmt))
