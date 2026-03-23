"""PostgreSQL tools for the MCP server.

All public async functions are the single source of truth for database I/O.
They are:
  - Registered as MCP tools in mcp_server/server.py (for external protocol access)
  - Imported directly by REST routes and agent nodes (same-process Python call)

Each function opens and closes its own AsyncSession so callers never manage
transactions directly.
"""
import base64
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import aliased, selectinload

from app.db.database import AsyncSessionLocal
from app.db.models import (
    CoachDocument,
    CoachingSession,
    Message,
    MessageRole,
    MethodologyDocument,
    SessionStatus,
    Tenant,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────── serializers ──────────────────────────────────

def _user_dict(u: User) -> dict:
    return {
        "id": str(u.id),
        "keycloak_sub": u.keycloak_sub,
        "email": u.email,
        "role": u.role.value,
        "tenant_id": str(u.tenant_id),
        "coach_id": str(u.coach_id) if u.coach_id else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _session_dict(
    s: CoachingSession,
    *,
    client_email: Optional[str] = None,
) -> dict:
    return {
        "id": str(s.id),
        "title": s.title,
        "client_id": str(s.client_id),
        "coach_id": str(s.coach_id) if s.coach_id else None,
        "tenant_id": str(s.tenant_id),
        "status": s.status.value,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "client_email": client_email,
    }


def _message_dict(m: Message) -> dict:
    return {
        "id": str(m.id),
        "session_id": str(m.session_id),
        "role": m.role.value,
        "content": m.content,
        "metadata_": m.metadata_ or {},
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _tenant_dict(t: Tenant) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "slug": t.slug,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tenant
# ═══════════════════════════════════════════════════════════════════════════════

async def pg_get_or_create_tenant(slug: str, name: str) -> dict:
    """Return existing tenant by slug or create a new one."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.slug == slug))
        tenant = result.scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name=name, slug=slug)
            db.add(tenant)
            await db.flush()
            await db.refresh(tenant)
        await db.commit()
        return _tenant_dict(tenant)


# ═══════════════════════════════════════════════════════════════════════════════
# User
# ═══════════════════════════════════════════════════════════════════════════════

async def pg_get_user_by_sub(keycloak_sub: str) -> Optional[dict]:
    """Fetch a user by Keycloak subject claim. Returns None if not found."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.keycloak_sub == keycloak_sub)
        )
        u = result.scalar_one_or_none()
        return _user_dict(u) if u else None


async def pg_get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch a user by internal UUID string. Returns None if not found."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        u = result.scalar_one_or_none()
        return _user_dict(u) if u else None


async def pg_get_users_by_ids(user_ids: list[str]) -> list[dict]:
    """Batch-fetch users by a list of UUID strings."""
    if not user_ids:
        return []
    async with AsyncSessionLocal() as db:
        uuids = [UUID(uid) for uid in user_ids]
        result = await db.execute(select(User).where(User.id.in_(uuids)))
        return [_user_dict(u) for u in result.scalars().all()]


async def pg_upsert_user(
    keycloak_sub: str,
    email: str,
    role: str,
    tenant_id: str,
) -> dict:
    """Create or update a user record from token claims.

    Role is only promoted (client → coach → admin), never downgraded.
    """
    # Import here to avoid circular import at module load time.
    from app.api.deps import _role_rank

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.keycloak_sub == keycloak_sub)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                keycloak_sub=keycloak_sub,
                email=email,
                role=UserRole(role),
                tenant_id=UUID(tenant_id),
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)
        else:
            if user.email != email:
                user.email = email
            new_role = UserRole(role)
            if _role_rank(new_role) > _role_rank(user.role):
                user.role = new_role
            if str(user.tenant_id) != tenant_id:
                user.tenant_id = UUID(tenant_id)
            await db.flush()
            await db.refresh(user)
        await db.commit()
        return _user_dict(user)


async def pg_list_users(
    tenant_id: str,
    role: Optional[str] = None,
) -> list[dict]:
    """List users in a tenant, optionally filtered by role."""
    async with AsyncSessionLocal() as db:
        stmt = select(User).where(User.tenant_id == UUID(tenant_id))
        if role:
            stmt = stmt.where(User.role == UserRole(role))
        result = await db.execute(stmt.order_by(User.email))
        return [_user_dict(u) for u in result.scalars().all()]


async def pg_assign_coach(client_id: str, coach_id: Optional[str]) -> bool:
    """Set or clear the coach assignment for a client user. Returns True if user found."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == UUID(client_id)))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.coach_id = UUID(coach_id) if coach_id else None
        await db.commit()
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# CoachingSession
# ═══════════════════════════════════════════════════════════════════════════════

async def pg_get_session(session_id: str) -> Optional[dict]:
    """Fetch a coaching session by UUID. Returns None if not found."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CoachingSession)
            .options(selectinload(CoachingSession.client))
            .where(CoachingSession.id == UUID(session_id))
        )
        s = result.scalar_one_or_none()
        if s is None:
            return None
        return _session_dict(s, client_email=s.client.email if s.client else None)


async def pg_get_session_with_messages(session_id: str) -> Optional[dict]:
    """Fetch a session with its full ordered message transcript."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CoachingSession)
            .options(
                selectinload(CoachingSession.messages),
                selectinload(CoachingSession.client),
            )
            .where(CoachingSession.id == UUID(session_id))
        )
        s = result.scalar_one_or_none()
        if s is None:
            return None
        data = _session_dict(s, client_email=s.client.email if s.client else None)
        data["messages"] = [_message_dict(m) for m in s.messages]
        return data


async def pg_list_sessions(
    tenant_id: str,
    *,
    client_id: Optional[str] = None,
    coach_id: Optional[str] = None,
) -> list[dict]:
    """List coaching sessions with optional role-based filters.

    - client_id only  → sessions owned by that client
    - coach_id only   → sessions for clients assigned to that coach
    - neither         → all sessions for the tenant (admin view)
    """
    async with AsyncSessionLocal() as db:
        if client_id is not None:
            stmt = (
                select(CoachingSession)
                .options(selectinload(CoachingSession.client))
                .where(CoachingSession.client_id == UUID(client_id))
                .order_by(CoachingSession.created_at.desc())
            )
        elif coach_id is not None:
            ClientUser = aliased(User)
            stmt = (
                select(CoachingSession)
                .options(selectinload(CoachingSession.client))
                .where(CoachingSession.tenant_id == UUID(tenant_id))
                .join(ClientUser, ClientUser.id == CoachingSession.client_id)
                .where(ClientUser.coach_id == UUID(coach_id))
                .order_by(CoachingSession.created_at.desc())
            )
        else:
            stmt = (
                select(CoachingSession)
                .options(selectinload(CoachingSession.client))
                .where(CoachingSession.tenant_id == UUID(tenant_id))
                .order_by(CoachingSession.created_at.desc())
            )
        result = await db.execute(stmt)
        sessions = result.scalars().all()
        return [
            _session_dict(s, client_email=s.client.email if s.client else None)
            for s in sessions
        ]


async def pg_get_last_messages_for_sessions(
    session_ids: list[str],
) -> dict[str, str]:
    """Return {session_id: last_message_content} for a batch of session IDs."""
    if not session_ids:
        return {}
    async with AsyncSessionLocal() as db:
        uuids = [UUID(sid) for sid in session_ids]
        latest_ts_sq = (
            select(Message.session_id, func.max(Message.created_at).label("max_ts"))
            .where(Message.session_id.in_(uuids))
            .group_by(Message.session_id)
            .subquery()
        )
        result = await db.execute(
            select(Message.session_id, Message.content).join(
                latest_ts_sq,
                and_(
                    Message.session_id == latest_ts_sq.c.session_id,
                    Message.created_at == latest_ts_sq.c.max_ts,
                ),
            )
        )
        return {str(row.session_id): row.content for row in result}


async def pg_create_session(
    tenant_id: str,
    client_id: str,
    title: str,
    coach_id: Optional[str] = None,
) -> dict:
    """Persist and return a new coaching session."""
    async with AsyncSessionLocal() as db:
        session = CoachingSession(
            title=title,
            client_id=UUID(client_id),
            coach_id=UUID(coach_id) if coach_id else None,
            tenant_id=UUID(tenant_id),
            status=SessionStatus.active,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        await db.commit()
        return _session_dict(session)


async def pg_update_session(
    session_id: str,
    *,
    title: Optional[str] = None,
    status: Optional[str] = None,
    coach_id: Optional[str] = None,
    clear_coach: bool = False,
) -> Optional[dict]:
    """Partial-update a coaching session. Returns updated dict or None if not found."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CoachingSession).where(CoachingSession.id == UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if session is None:
            return None
        if title is not None:
            session.title = title
        if status is not None:
            session.status = SessionStatus(status)
        if coach_id is not None:
            session.coach_id = UUID(coach_id)
        elif clear_coach:
            session.coach_id = None
        await db.flush()
        await db.refresh(session)
        await db.commit()
        return _session_dict(session)


async def pg_delete_session(session_id: str) -> bool:
    """Delete a session and all its messages. Returns True if found and deleted."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CoachingSession).where(CoachingSession.id == UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        await db.execute(delete(Message).where(Message.session_id == UUID(session_id)))
        await db.delete(session)
        await db.commit()
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# Message
# ═══════════════════════════════════════════════════════════════════════════════

async def pg_get_session_messages(session_id: str) -> list[dict]:
    """Return all messages for a session ordered by creation time (oldest first)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Message)
            .where(Message.session_id == UUID(session_id))
            .order_by(Message.created_at.asc())
        )
        return [_message_dict(m) for m in result.scalars().all()]


async def pg_append_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None,
) -> dict:
    """Append a message to a session and return the persisted record."""
    async with AsyncSessionLocal() as db:
        msg = Message(
            session_id=UUID(session_id),
            role=MessageRole(role),
            content=content,
            metadata_=metadata or {},
        )
        db.add(msg)
        await db.flush()
        await db.refresh(msg)
        await db.commit()
        return _message_dict(msg)


# ═══════════════════════════════════════════════════════════════════════════════
# CoachDocument
# ═══════════════════════════════════════════════════════════════════════════════

async def pg_save_coach_document(
    doc_id: str,
    coach_id: str,
    client_id: str,
    tenant_id: str,
    filename: str,
    content_type: str,
    file_bytes_b64: str,
    uploaded_at: str,
) -> dict:
    """Persist a coach document's file bytes to PostgreSQL.

    ``file_bytes_b64`` must be a standard base64-encoded string of the raw bytes.
    """
    file_bytes = base64.b64decode(file_bytes_b64)
    async with AsyncSessionLocal() as db:
        doc = CoachDocument(
            doc_id=doc_id,
            coach_id=UUID(coach_id),
            client_id=UUID(client_id),
            tenant_id=UUID(tenant_id),
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
            uploaded_at=datetime.fromisoformat(uploaded_at),
            is_active=True,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)
        await db.commit()
        return {
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "client_id": str(doc.client_id),
            "coach_id": str(doc.coach_id),
            "tenant_id": str(doc.tenant_id),
            "content_type": doc.content_type,
            "uploaded_at": doc.uploaded_at.isoformat(),
            "is_active": doc.is_active,
        }


async def pg_get_coach_document(doc_id: str) -> Optional[dict]:
    """Fetch an active coach document including file bytes (base64-encoded).

    Returns None if the document is not found or has been archived.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CoachDocument).where(
                CoachDocument.doc_id == doc_id,
                CoachDocument.is_active == True,  # noqa: E712
            )
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            return None
        return {
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "content_type": doc.content_type,
            "file_bytes_b64": base64.b64encode(doc.file_bytes).decode(),
            "client_id": str(doc.client_id),
            "coach_id": str(doc.coach_id),
            "tenant_id": str(doc.tenant_id),
            "uploaded_at": doc.uploaded_at.isoformat(),
        }


async def pg_archive_coach_document(doc_id: str) -> bool:
    """Soft-delete a coach document by marking it inactive. Returns True if found."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CoachDocument).where(
                CoachDocument.doc_id == doc_id,
                CoachDocument.is_active == True,  # noqa: E712
            )
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            return False
        doc.is_active = False
        await db.commit()
        return True


async def pg_list_active_coach_documents(
    tenant_id: str,
    coach_id: str,
    client_id: Optional[str] = None,
) -> list[dict]:
    """List active coach documents owned by a coach, optionally filtered by client."""
    async with AsyncSessionLocal() as db:
        stmt = select(CoachDocument).where(
            CoachDocument.tenant_id == UUID(tenant_id),
            CoachDocument.coach_id == UUID(coach_id),
            CoachDocument.is_active == True,  # noqa: E712
        )
        if client_id:
            stmt = stmt.where(CoachDocument.client_id == UUID(client_id))
        result = await db.execute(stmt.order_by(CoachDocument.uploaded_at.desc()))
        return [
            {
                "doc_id": d.doc_id,
                "filename": d.filename,
                "client_id": str(d.client_id),
                "coach_id": str(d.coach_id),
                "content_type": d.content_type,
                "uploaded_at": d.uploaded_at.isoformat(),
            }
            for d in result.scalars().all()
        ]


# ─────────────────────────── methodology documents ────────────────────────────

async def pg_save_methodology_document(
    doc_id: str,
    tenant_id: str,
    filename: str,
    content_type: str,
    file_bytes_b64: str,
    uploaded_by: str,
    uploaded_at: str,
) -> dict:
    """Persist raw bytes for an admin-uploaded methodology document."""
    file_bytes = base64.b64decode(file_bytes_b64)
    async with AsyncSessionLocal() as db:
        doc = MethodologyDocument(
            doc_id=doc_id,
            tenant_id=UUID(tenant_id),
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
            uploaded_at=datetime.fromisoformat(uploaded_at),
            uploaded_by=UUID(uploaded_by),
            is_active=True,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return {
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "content_type": doc.content_type,
            "uploaded_at": doc.uploaded_at.isoformat(),
        }


async def pg_get_methodology_document(doc_id: str) -> Optional[dict]:
    """Return the raw file bytes (base64-encoded) for an active methodology document."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MethodologyDocument).where(
                MethodologyDocument.doc_id == doc_id,
                MethodologyDocument.is_active == True,  # noqa: E712
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return None
        return {
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "content_type": doc.content_type,
            "file_bytes_b64": base64.b64encode(doc.file_bytes).decode(),
            "uploaded_at": doc.uploaded_at.isoformat(),
        }


async def pg_archive_methodology_document(doc_id: str) -> bool:
    """Soft-delete a methodology document row (is_active → False). Returns True if found."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MethodologyDocument).where(
                MethodologyDocument.doc_id == doc_id,
                MethodologyDocument.is_active == True,  # noqa: E712
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return False
        doc.is_active = False
        await db.commit()
        return True


async def pg_update_methodology_document(
    doc_id: str,
    filename: str,
    content_type: str,
    file_bytes_b64: str,
    uploaded_by: str,
    uploaded_at: str,
) -> bool:
    """Replace the file bytes on an existing methodology document row in-place."""
    file_bytes = base64.b64decode(file_bytes_b64)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MethodologyDocument).where(MethodologyDocument.doc_id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return False
        doc.filename = filename
        doc.content_type = content_type
        doc.file_bytes = file_bytes
        doc.uploaded_at = datetime.fromisoformat(uploaded_at)
        doc.uploaded_by = UUID(uploaded_by)
        doc.is_active = True
        await db.commit()
        return True
