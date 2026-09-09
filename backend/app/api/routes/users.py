import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_manager
from app.core.security import hash_password
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole
from app.schemas.user import (
    UserCreatedResponse,
    UserCreateRequest,
    UserRead,
    UserResetPasswordResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["users"])


def _generate_password() -> str:
    # 12 символов, безопасный алфавит без неоднозначных символов
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _get_target_or_404(user_id: int, db: Session, actor: User) -> User:
    target = db.get(User, user_id)
    if target is None or target.company_id != actor.company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return target


def _ensure_can_manage(actor: User, target: User, new_role: UserRole | None = None) -> None:
    """Правила управления: админ может всё; руководитель ПТО не трогает админов и не выдаёт роль админа."""
    role = new_role or target.role
    if actor.role == UserRole.PTO_HEAD and (target.role == UserRole.ADMIN or role == UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для этой операции"
        )
    if target.id == actor.id and new_role and new_role != actor.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя изменить собственную роль"
        )


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db), actor: User = Depends(require_manager)
) -> list[User]:
    return list(db.scalars(select(User).where(User.company_id == actor.company_id).order_by(User.full_name)))


@router.post("", response_model=UserCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager),
) -> UserCreatedResponse:
    # Только администратор может создавать администраторов
    if body.role == UserRole.ADMIN and actor.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для этой операции"
        )
    email = body.email.lower()
    existing = db.scalar(
        select(User).where(User.company_id == actor.company_id, User.email == email)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Пользователь с таким email уже существует"
        )
    password = _generate_password()
    user = User(
        company_id=actor.company_id,
        email=email,
        full_name=body.full_name.strip(),
        role=body.role,
        password_hash=hash_password(password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Пользователь с таким email уже существует"
        ) from None
    db.refresh(user)
    return UserCreatedResponse(user=UserRead.model_validate(user), generated_password=password)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    body: UserUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager),
) -> User:
    target = _get_target_or_404(user_id, db, actor)
    _ensure_can_manage(actor, target, new_role=body.role)
    if body.full_name is not None:
        target.full_name = body.full_name.strip()
    if body.role is not None:
        target.role = body.role
    if body.is_active is not None and target.id != actor.id:
        target.is_active = body.is_active
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


@router.post("/{user_id}/reset-password", response_model=UserResetPasswordResponse)
def reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager),
) -> UserResetPasswordResponse:
    target = _get_target_or_404(user_id, db, actor)
    _ensure_can_manage(actor, target)
    password = _generate_password()
    target.password_hash = hash_password(password)
    target.token_version += 1  # инвалидируем все refresh-токены пользователя
    db.add(target)
    db.commit()
    db.refresh(target)
    return UserResetPasswordResponse(
        user=UserRead.model_validate(target), generated_password=password
    )
