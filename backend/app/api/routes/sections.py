"""Шифры рабочей документации внутри объекта (рабочая область)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_manager, require_object_access
from app.db.session import get_db
from app.models import ConstructionObject, ObjectFile, RdSection, User
from app.schemas.sections import SectionCreateRequest, SectionRead, SectionUpdateRequest

router = APIRouter(prefix="/objects/{object_id}/sections", tags=["sections"])


@router.get("", response_model=list[SectionRead])
def list_sections(
    object_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> list[RdSection]:
    stmt = select(RdSection).where(RdSection.object_id == obj.id).order_by(
        RdSection.sort_order, RdSection.code
    )
    return list(db.scalars(stmt))


@router.post("", response_model=SectionRead, status_code=status.HTTP_201_CREATED)
def create_section(
    object_id: int,
    body: SectionCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager),
    obj: ConstructionObject = Depends(require_object_access),
) -> RdSection:
    section = RdSection(
        company_id=obj.company_id,
        object_id=obj.id,
        code=body.code.strip(),
        name=body.name.strip() if body.name else None,
        sort_order=body.sort_order,
    )
    db.add(section)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Шифр с таким кодом уже существует в объекте"
        ) from None
    db.refresh(section)
    return section


@router.patch("/{section_id}", response_model=SectionRead)
def update_section(
    object_id: int,
    section_id: int,
    body: SectionUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager),
    obj: ConstructionObject = Depends(require_object_access),
) -> RdSection:
    section = db.scalar(
        select(RdSection).where(RdSection.id == section_id, RdSection.object_id == obj.id)
    )
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шифр не найден")
    if body.code is not None:
        section.code = body.code.strip()
    if body.name is not None:
        section.name = body.name.strip() or None
    if body.sort_order is not None:
        section.sort_order = body.sort_order
    db.add(section)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Шифр с таким кодом уже существует в объекте"
        ) from None
    db.refresh(section)
    return section


@router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(
    object_id: int,
    section_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager),
    obj: ConstructionObject = Depends(require_object_access),
) -> None:
    section = db.scalar(
        select(RdSection).where(RdSection.id == section_id, RdSection.object_id == obj.id)
    )
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шифр не найден")
    file_count = db.scalar(
        select(func.count()).select_from(ObjectFile).where(ObjectFile.section_id == section.id)
    )
    if file_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="В шифре есть файлы — удалите их или перенесите в другой шифр",
        )
    db.delete(section)
    db.commit()
