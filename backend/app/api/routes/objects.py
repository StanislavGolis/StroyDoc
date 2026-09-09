from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_manager, require_object_access
from app.db.session import get_db
from app.models import ConstructionObject, ObjectAssignment, User
from app.models.enums import ObjectStatus, UserRole
from app.schemas.object import (
    AssignmentCreateRequest,
    AssignmentRead,
    AssignmentUserRead,
    ObjectCreateRequest,
    ObjectRead,
    ObjectUpdateRequest,
)

router = APIRouter(prefix="/objects", tags=["objects"])


@router.get("", response_model=list[ObjectRead])
def list_objects(
    q: str | None = Query(default=None, max_length=100),
    status_filter: ObjectStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ConstructionObject]:
    """Список объектов. Инженер видит только назначенные ему объекты."""
    stmt = select(ConstructionObject).where(ConstructionObject.company_id == user.company_id)
    if not user.is_manager:
        stmt = stmt.join(ObjectAssignment, ObjectAssignment.object_id == ConstructionObject.id).where(
            ObjectAssignment.user_id == user.id
        )
    if status_filter is not None:
        stmt = stmt.where(ConstructionObject.status == status_filter)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (ConstructionObject.name.ilike(like)) | (ConstructionObject.code.ilike(like))
        )
    stmt = stmt.order_by(ConstructionObject.created_at.desc(), ConstructionObject.id.desc())
    return list(db.scalars(stmt))


@router.post("", response_model=ObjectRead, status_code=status.HTTP_201_CREATED)
def create_object(
    body: ObjectCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager),
) -> ConstructionObject:
    obj = ConstructionObject(
        company_id=actor.company_id,
        name=body.name.strip(),
        code=body.code.strip() if body.code else None,
        start_date=body.start_date,
        end_date=body.end_date,
        status=body.status,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{object_id}", response_model=ObjectRead)
def get_object(obj: ConstructionObject = Depends(require_object_access)) -> ConstructionObject:
    return obj


@router.patch("/{object_id}", response_model=ObjectRead)
def update_object(
    object_id: int,
    body: ObjectUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager),
    obj: ConstructionObject = Depends(require_object_access),
) -> ConstructionObject:
    if body.name is not None:
        obj.name = body.name.strip()
    if body.code is not None:
        obj.code = body.code.strip()
    if body.start_date is not None:
        obj.start_date = body.start_date
    if body.end_date is not None:
        obj.end_date = body.end_date
    if body.status is not None:
        obj.status = body.status
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/{object_id}/assignments", response_model=list[AssignmentRead])
def list_assignments(
    object_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    obj: ConstructionObject = Depends(require_object_access),
) -> list[AssignmentRead]:
    assignments = db.scalars(
        select(ObjectAssignment)
        .options(selectinload(ObjectAssignment.user))
        .where(ObjectAssignment.object_id == obj.id)
        .order_by(ObjectAssignment.created_at)
    )
    return [
        AssignmentRead(
            id=a.id,
            object_id=a.object_id,
            created_at=a.created_at,
            user=AssignmentUserRead(
                id=a.user.id, full_name=a.user.full_name, email=a.user.email, role=a.user.role
            ),
        )
        for a in assignments
    ]


@router.post(
    "/{object_id}/assignments",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_assignment(
    object_id: int,
    body: AssignmentCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager),
    obj: ConstructionObject = Depends(require_object_access),
) -> AssignmentRead:
    target = db.get(User, body.user_id)
    if target is None or target.company_id != actor.company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    if target.role != UserRole.PTO_ENGINEER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Назначать на объект можно только инженеров ПТО",
        )
    assignment = ObjectAssignment(object_id=obj.id, user_id=target.id, created_by=actor.id)
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Инженер уже назначен на объект"
        ) from None
    db.refresh(assignment)
    return AssignmentRead(
        id=assignment.id,
        object_id=assignment.object_id,
        created_at=assignment.created_at,
        user=AssignmentUserRead(
            id=target.id, full_name=target.full_name, email=target.email, role=target.role
        ),
    )


@router.delete("/{object_id}/assignments/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_assignment(
    object_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager),
    obj: ConstructionObject = Depends(require_object_access),
) -> None:
    assignment = db.scalar(
        select(ObjectAssignment).where(
            ObjectAssignment.object_id == obj.id, ObjectAssignment.user_id == user_id
        )
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Назначение не найдено")
    db.delete(assignment)
    db.commit()

