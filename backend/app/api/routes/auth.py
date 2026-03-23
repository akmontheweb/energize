import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from app.api.deps import get_current_user, get_current_token_user
from app.core.config import settings
from app.db.models import User
from app.schemas.user import TokenUser, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters")
        return v


# Description: Function `get_me` implementation.
# Inputs: current_user
# Output: UserRead
# Exceptions: Propagates exceptions raised by internal operations.
@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Return the current authenticated user's profile."""
    logger.info("Returned authenticated profile user_id=%s role=%s", current_user.id, current_user.role.value)
    return UserRead.model_validate(current_user)


# Description: Function `get_token_info` implementation.
# Inputs: token_user
# Output: Varies by implementation
# Exceptions: Propagates exceptions raised by internal operations.
@router.get("/token-info")
async def get_token_info(token_user: TokenUser = Depends(get_current_token_user)):
    """Return decoded token claims (for debugging)."""
    logger.info("Returned token info sub=%s tenant_id=%s role_count=%s", token_user.sub, token_user.tenant_id, len(token_user.roles))
    return token_user


@router.post("/change-password", status_code=200)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
):
    """Validate the current password then change it via the Keycloak Admin API."""
    token_url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        "/protocol/openid-connect/token"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        # Step 1: validate current password via ROPC grant
        verify_resp = await client.post(
            token_url,
            data={
                "grant_type": "password",
                "client_id": settings.KEYCLOAK_CLIENT_ID,
                "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                "username": current_user.email,
                "password": body.current_password,
            },
        )
        if verify_resp.status_code != 200:
            logger.warning("change-password: current password invalid for user_id=%s", current_user.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        # Step 2: get admin token from master realm
        admin_token_resp = await client.post(
            f"{settings.KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": settings.KEYCLOAK_ADMIN,
                "password": settings.KEYCLOAK_ADMIN_PASSWORD,
            },
        )
        if admin_token_resp.status_code != 200:
            logger.error("change-password: failed to obtain admin token")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to authenticate with identity provider",
            )
        admin_token = admin_token_resp.json()["access_token"]

        # Step 3: reset password via Keycloak Admin REST API
        reset_resp = await client.put(
            f"{settings.KEYCLOAK_URL}/admin/realms/{settings.KEYCLOAK_REALM}"
            f"/users/{current_user.keycloak_sub}/reset-password",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"type": "password", "value": body.new_password, "temporary": False},
        )
        if reset_resp.status_code not in (200, 204):
            logger.error(
                "change-password: reset-password API failed status=%s user_id=%s",
                reset_resp.status_code, current_user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password",
            )

    logger.info("change-password: password changed successfully for user_id=%s", current_user.id)
    return {"message": "Password changed successfully"}
