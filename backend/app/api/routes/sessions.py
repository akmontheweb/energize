import logging
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status

from app.api.deps import get_current_user
from app.db.models import User
from app.schemas.session import MessageRead, SessionCreate, SessionRead, SessionUpdate, SessionWithMessages
from mcp_server.tools.postgres import (
    pg_create_session,
    pg_delete_session,
    pg_get_last_messages_for_sessions,
    pg_get_session,
    pg_get_session_messages,
    pg_get_session_with_messages,
    pg_get_user_by_id,
    pg_list_sessions,
    pg_update_session,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


async def _assert_coach_client_access(coach_id: str, client_id: str) -> None:
    """Raise 403 if the session's client is not assigned to the coach."""
    client = await pg_get_user_by_id(client_id)
    if not client or client.get("coach_id") != coach_id:
        raise HTTPException(status_code=403, detail="Not authorized")


# Description: Function `list_sessions` implementation.
@router.get("", response_model=List[SessionRead])
async def list_sessions(
    client_id: Optional[str] = Query(None, description="Admin only: filter sessions by client UUID"),
    current_user: User = Depends(get_current_user),
) -> List[SessionRead]:
    """List all sessions for the current user filtered by tenant."""
    role = current_user.role.value
    tenant_id = str(current_user.tenant_id)

    if role == "coach":
        sessions_data = await pg_list_sessions(tenant_id, coach_id=str(current_user.id))
    elif role == "admin":
        sessions_data = await pg_list_sessions(
            tenant_id, client_id=client_id if client_id else None
        )
    else:
        sessions_data = await pg_list_sessions(tenant_id, client_id=str(current_user.id))

    session_ids = [s["id"] for s in sessions_data]
    last_msgs = await pg_get_last_messages_for_sessions(session_ids)

    logger.info(
        "Listed sessions user_id=%s role=%s tenant_id=%s count=%s",
        current_user.id,
        role,
        tenant_id,
        len(sessions_data),
    )

    out = []
    for s in sessions_data:
        sr = SessionRead.model_validate(s)
        updates: dict = {"last_message": last_msgs.get(s["id"])}
        if role in ("coach", "admin") and s.get("client_email"):
            updates["client_email"] = s["client_email"]
        out.append(sr.model_copy(update=updates))
    return out


# Description: Function `create_session` implementation.
@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate = Body(default_factory=SessionCreate),
    current_user: User = Depends(get_current_user),
) -> SessionRead:
    """Create a new coaching session. Clients only."""
    if current_user.role.value != "client":
        logger.warning(
            "Rejected session creation user_id=%s role=%s", current_user.id, current_user.role.value
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can start a session.",
        )

    title = (payload.title or "").strip() or "New Coaching Session"
    coach_id = (
        str(payload.coach_id)
        if payload.coach_id
        else (str(current_user.coach_id) if current_user.coach_id else None)
    )

    session_data = await pg_create_session(
        tenant_id=str(current_user.tenant_id),
        client_id=str(current_user.id),
        title=title,
        coach_id=coach_id,
    )
    logger.info(
        "Created session session_id=%s client_id=%s coach_id=%s tenant_id=%s",
        session_data["id"],
        session_data["client_id"],
        session_data["coach_id"],
        session_data["tenant_id"],
    )
    return SessionRead.model_validate(session_data)


# Description: Function `get_session` implementation.
@router.get("/{session_id}", response_model=SessionWithMessages)
async def get_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
) -> SessionWithMessages:
    """Get a session with its full message transcript."""
    session_data = await pg_get_session_with_messages(str(session_id))

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_data["tenant_id"] != str(current_user.tenant_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.role.value == "client" and session_data["client_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.role.value == "coach":
        await _assert_coach_client_access(str(current_user.id), session_data["client_id"])

    return SessionWithMessages.model_validate(session_data)


# Description: Function `list_session_messages` implementation.
@router.get("/{session_id}/messages", response_model=List[MessageRead])
async def list_session_messages(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
) -> List[MessageRead]:
    """List messages for a session with tenant and role authorization checks."""
    session_data = await pg_get_session(str(session_id))

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_data["tenant_id"] != str(current_user.tenant_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.role.value == "client" and session_data["client_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.role.value == "coach":
        await _assert_coach_client_access(str(current_user.id), session_data["client_id"])

    msgs = await pg_get_session_messages(str(session_id))
    return [MessageRead.model_validate(m) for m in msgs]


# Description: Function `update_session` implementation.
@router.patch("/{session_id}", response_model=SessionRead)
async def update_session(
    session_id: UUID,
    payload: SessionUpdate,
    current_user: User = Depends(get_current_user),
) -> SessionRead:
    """Update session status, title, or coach assignment."""
    session_data = await pg_get_session(str(session_id))

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_data["tenant_id"] != str(current_user.tenant_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    kwargs: dict = {}
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        kwargs["title"] = title
    if payload.status is not None:
        from app.db.models import SessionStatus
        try:
            SessionStatus(payload.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")
        kwargs["status"] = payload.status
    if payload.coach_id is not None:
        kwargs["coach_id"] = str(payload.coach_id)

    updated = await pg_update_session(str(session_id), **kwargs)
    logger.info("Updated session session_id=%s actor_id=%s", session_id, current_user.id)
    return SessionRead.model_validate(updated)


# Description: Function `delete_session` implementation.
@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a session and its messages with tenant and role authorization checks."""
    session_data = await pg_get_session(str(session_id))

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_data["tenant_id"] != str(current_user.tenant_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.role.value == "client" and session_data["client_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    if current_user.role.value == "coach" and session_data.get("coach_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    await pg_delete_session(str(session_id))
    logger.info("Deleted session session_id=%s actor_id=%s", session_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

