import logging
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import verify_token
from app.db.database import AsyncSessionLocal
from app.db.models import User, Tenant, UserRole
from app.schemas.user import TokenUser

security = HTTPBearer()
logger = logging.getLogger(__name__)


# Description: Function `_resolve_role_from_claims` implementation.
# Inputs: raw_roles
# Output: UserRole
# Exceptions: Propagates exceptions raised by internal operations.
def _resolve_role_from_claims(raw_roles: list[str]) -> UserRole:
    """Map token roles to application roles, including common Keycloak aliases."""
    roles = {r.lower() for r in raw_roles}
    admin_aliases = {"admin", "realm-admin", "super-admin", "super_admin"}
    coach_aliases = {"coach", "energize-coach"}
    if roles.intersection(admin_aliases):
        return UserRole.admin
    if roles.intersection(coach_aliases):
        return UserRole.coach
    return UserRole.client


# Description: Function `_role_rank` implementation.
# Inputs: role
# Output: int
# Exceptions: Propagates exceptions raised by internal operations.
def _role_rank(role: UserRole) -> int:
    """Return precedence for safe role synchronization decisions."""
    ranks = {
        UserRole.client: 1,
        UserRole.coach: 2,
        UserRole.admin: 3,
    }
    return ranks[role]


# Description: Function `get_db` implementation.
# Inputs: None
# Output: AsyncGenerator[AsyncSession, None]
# Exceptions: Propagates exceptions raised by internal operations.
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Description: Function `get_current_token_user` implementation.
# Inputs: credentials
# Output: TokenUser
# Exceptions: Propagates exceptions raised by internal operations.
async def get_current_token_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenUser:
    token_data = await verify_token(credentials.credentials)
    logger.info(
        "Decoded token claims sub=%s email=%s tenant_id=%s roles=%s",
        token_data.get("sub"),
        token_data.get("email"),
        token_data.get("tenant_id"),
        token_data.get("roles"),
    )
    return TokenUser(**token_data)


# Description: Function `get_current_user` implementation.
# Inputs: token_user, db
# Output: User
# Exceptions: Propagates exceptions raised by internal operations.
async def get_current_user(
    token_user: TokenUser = Depends(get_current_token_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    token_role = _resolve_role_from_claims(token_user.roles)
    logger.info(
        "Resolved token role sub=%s email=%s raw_roles=%s resolved_role=%s",
        token_user.sub,
        token_user.email,
        token_user.roles,
        token_role.value,
    )

    result = await db.execute(
        select(User).where(User.keycloak_sub == token_user.sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Auto-provision user on first login
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.slug == token_user.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

        if tenant is None:
            tenant = Tenant(name=token_user.tenant_id, slug=token_user.tenant_id)
            db.add(tenant)
            await db.flush()

        user = User(
            keycloak_sub=token_user.sub,
            email=token_user.email,
            role=token_role,
            tenant_id=tenant.id,
        )
        db.add(user)
        await db.flush()
        logger.info(
            "Auto-provisioned user sub=%s tenant_id=%s role=%s",
            token_user.sub,
            tenant.id,
            token_role.value,
        )
    else:
        # Keep role and email in sync with token claims.
        # Only allow role upgrades from token claims; never downgrade an existing privileged role.
        if _role_rank(token_role) > _role_rank(user.role):
            logger.info(
                "Upgrading user role from token claims sub=%s old_role=%s new_role=%s",
                token_user.sub,
                user.role.value,
                token_role.value,
            )
            user.role = token_role
        elif _role_rank(token_role) < _role_rank(user.role):
            logger.warning(
                "Ignored role downgrade from token claims sub=%s existing_role=%s token_role=%s",
                token_user.sub,
                user.role.value,
                token_role.value,
            )
        if token_user.email and user.email != token_user.email:
            logger.info(
                "Synchronizing user email sub=%s old_email=%s new_email=%s",
                token_user.sub,
                user.email,
                token_user.email,
            )
            user.email = token_user.email

    return user


# Description: Function `get_tenant_id` implementation.
# Inputs: current_user
# Output: str
# Exceptions: Propagates exceptions raised by internal operations.
async def get_tenant_id(
    current_user: User = Depends(get_current_user),
) -> str:
    return str(current_user.tenant_id)
