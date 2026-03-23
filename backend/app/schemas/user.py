from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# Description: Class `UserBase` encapsulates related data and behavior for this module.
class UserBase(BaseModel):
    """Fields shared by user read and write schemas."""

    email: str
    role: str


# Description: Class `UserCreate` encapsulates related data and behavior for this module.
class UserCreate(UserBase):
    """Payload used when creating a user record from external identity claims."""

    keycloak_sub: str
    tenant_id: UUID


# Description: Class `UserRead` encapsulates related data and behavior for this module.
class UserRead(UserBase):
    """Serialized user model returned to API consumers."""

    id: UUID
    keycloak_sub: str
    tenant_id: UUID
    coach_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# Description: Class `UserUpdate` encapsulates related data and behavior for this module.
class UserUpdate(BaseModel):
    """Admin-managed user updates.

    `coach_id` accepts either a coach UUID or `null` to clear the assignment.
    """

    coach_id: Optional[UUID] = None


# Description: Class `TokenUser` encapsulates related data and behavior for this module.
class TokenUser(BaseModel):
    """Normalized token claims extracted from the upstream identity provider."""

    sub: str
    email: str
    roles: list[str]
    tenant_id: str
