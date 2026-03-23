import logging
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_user
from app.db.models import User, UserRole
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)


# Description: Function `_require_admin` implementation.
# Inputs: current_user
# Output: None
# Exceptions: Propagates exceptions raised by internal operations.
def _require_admin(current_user: User) -> None:
    """Reject non-admin requests for admin-only user management operations."""
    if current_user.role != UserRole.admin:
        logger.warning("Rejected admin-only user operation requester_id=%s role=%s", current_user.id, current_user.role.value)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


# Description: Function `_get_tenant_user` implementation.
# Inputs: db, current_user, user_id
# Output: User
# Exceptions: Propagates exceptions raised by internal operations.
async def _get_tenant_user(db: AsyncSession, current_user: User, user_id: UUID) -> User:
    """Load a user and enforce that it belongs to the caller's tenant."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.tenant_id != current_user.tenant_id:
        logger.warning("Rejected cross-tenant user operation requester_id=%s target_user_id=%s", current_user.id, user_id)
        raise HTTPException(status_code=403, detail="Not authorized")
    return user


# Description: Function `_get_tenant_coach` implementation.
# Inputs: db, current_user, coach_id
# Output: User
# Exceptions: Propagates exceptions raised by internal operations.
async def _get_tenant_coach(db: AsyncSession, current_user: User, coach_id: UUID) -> User:
    """Load a coach and ensure it belongs to the same tenant as the acting admin."""
    coach = await _get_tenant_user(db, current_user, coach_id)
    if coach.role != UserRole.coach:
        raise HTTPException(status_code=400, detail="Invalid coach. The selected user is not a coach.")
    return coach


# Description: Function `list_coaches` implementation.
# Inputs: current_user, db
# Output: List[UserRead]
# Exceptions: Propagates exceptions raised by internal operations.
@router.get("/coaches", response_model=List[UserRead])
async def list_coaches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserRead]:
    """List all coaches in the current tenant. Available to all authenticated users."""
    result = await db.execute(
        select(User).where(
            User.tenant_id == current_user.tenant_id,
            User.role == UserRole.coach,
        ).order_by(User.email)
    )
    coaches = result.scalars().all()
    logger.info(
        "Listed coaches requester_id=%s tenant_id=%s count=%s",
        current_user.id,
        current_user.tenant_id,
        len(coaches),
    )
    return [UserRead.model_validate(u) for u in coaches]


# Description: Function `list_users` implementation.
# Inputs: current_user, db
# Output: List[UserRead]
# Exceptions: Propagates exceptions raised by internal operations.
@router.get("", response_model=List[UserRead])
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserRead]:
    """Admin only: list all users in the tenant."""
    _require_admin(current_user)

    result = await db.execute(
        select(User).where(User.tenant_id == current_user.tenant_id).order_by(User.email)
    )
    users = result.scalars().all()
    logger.info("Listed users admin_id=%s tenant_id=%s count=%s", current_user.id, current_user.tenant_id, len(users))
    return [UserRead.model_validate(u) for u in users]


# Description: Function `update_user` implementation.
# Inputs: user_id, payload, current_user, db
# Output: UserRead
# Exceptions: Propagates exceptions raised by internal operations.
@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Admin only: assign or clear the single coach associated with a client."""
    _require_admin(current_user)
    user = await _get_tenant_user(db, current_user, user_id)
    if user.role != UserRole.client:
        raise HTTPException(status_code=400, detail="Only client users can be assigned to a coach.")

    if "coach_id" not in payload.model_fields_set:
        raise HTTPException(status_code=400, detail="coach_id must be supplied to assign or clear a coach.")

    if payload.coach_id is None:
        user.coach_id = None
        logger.info("Cleared coach assignment admin_id=%s client_id=%s", current_user.id, user.id)
    else:
        coach = await _get_tenant_coach(db, current_user, payload.coach_id)
        user.coach_id = coach.id
        logger.info("Assigned coach admin_id=%s client_id=%s coach_id=%s", current_user.id, user.id, coach.id)

    await db.flush()
    await db.refresh(user)
    return UserRead.model_validate(user)


# Description: Function `list_clients_for_coach` implementation.
# Inputs: coach_id, current_user, db
# Output: List[UserRead]
# Exceptions: Propagates exceptions raised by internal operations.
@router.get("/coaches/{coach_id}/clients", response_model=List[UserRead])
async def list_clients_for_coach(
    coach_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserRead]:
    """Admin only: list all clients currently assigned to a specific coach."""
    _require_admin(current_user)
    coach = await _get_tenant_coach(db, current_user, coach_id)

    result = await db.execute(
        select(User).where(
            User.tenant_id == current_user.tenant_id,
            User.role == UserRole.client,
            User.coach_id == coach.id,
        ).order_by(User.email)
    )
    clients = result.scalars().all()
    logger.info("Listed assigned clients admin_id=%s coach_id=%s count=%s", current_user.id, coach.id, len(clients))
    return [UserRead.model_validate(client) for client in clients]


# Description: Function `unassign_coach` implementation.
# Inputs: user_id, current_user, db
# Output: None
# Exceptions: Propagates exceptions raised by internal operations.
@router.delete("/{user_id}/coach", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_coach(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Admin only: remove the coach assignment from a client."""
    _require_admin(current_user)
    user = await _get_tenant_user(db, current_user, user_id)
    if user.role != UserRole.client:
        raise HTTPException(status_code=400, detail="Only client users can be unassigned from a coach.")

    user.coach_id = None
    await db.flush()
    logger.info("Unassigned coach admin_id=%s client_id=%s", current_user.id, user.id)


@router.get("/my-clients", response_model=List[UserRead])
async def list_my_clients(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserRead]:
    """Coach only: list all clients currently assigned to the authenticated coach."""
    if current_user.role != UserRole.coach:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Coach access required")

    result = await db.execute(
        select(User).where(
            User.tenant_id == current_user.tenant_id,
            User.role == UserRole.client,
            User.coach_id == current_user.id,
        ).order_by(User.email)
    )
    clients = result.scalars().all()
    logger.info(
        "Listed own clients coach_id=%s tenant_id=%s count=%s",
        current_user.id,
        current_user.tenant_id,
        len(clients),
    )
    return [UserRead.model_validate(u) for u in clients]
