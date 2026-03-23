from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


# Description: Class `MessageRead` encapsulates related data and behavior for this module.
class MessageRead(BaseModel):
    """API representation of a persisted session message."""

    id: UUID
    session_id: UUID
    role: str
    content: str
    metadata: Optional[Any] = Field(default=None, validation_alias="metadata_")
    created_at: datetime

    model_config = {"from_attributes": True}


# Description: Class `SessionCreate` encapsulates related data and behavior for this module.
class SessionCreate(BaseModel):
    """Client request used to start a new coaching session."""

    title: Optional[str] = None
    coach_id: Optional[UUID] = None


# Description: Class `SessionUpdate` encapsulates related data and behavior for this module.
class SessionUpdate(BaseModel):
    """Partial session update payload for title, status, or coach reassignment."""

    title: Optional[str] = None
    status: Optional[str] = None
    coach_id: Optional[UUID] = None


# Description: Class `SessionRead` encapsulates related data and behavior for this module.
class SessionRead(BaseModel):
    """Serialized session record returned by the REST API."""

    id: UUID
    title: Optional[str] = None
    client_id: UUID
    coach_id: Optional[UUID]
    tenant_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    # Populated server-side for coach/admin views
    client_email: Optional[str] = None
    # Snippet of the most recent message exchanged in this session
    last_message: Optional[str] = None

    model_config = {"from_attributes": True}


# Description: Class `SessionWithMessages` encapsulates related data and behavior for this module.
class SessionWithMessages(SessionRead):
    """Session record that also includes the full ordered transcript."""

    messages: List[MessageRead] = []
