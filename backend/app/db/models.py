import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Enum, Boolean, LargeBinary
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


# Description: Class `UserRole` encapsulates related data and behavior for this module.
class UserRole(str, PyEnum):
    """Supported application roles used for authorization decisions."""

    client = "client"
    coach = "coach"
    admin = "admin"


# Description: Class `SessionStatus` encapsulates related data and behavior for this module.
class SessionStatus(str, PyEnum):
    """Lifecycle states for a coaching session."""

    active = "active"
    completed = "completed"
    escalated = "escalated"
    archived = "archived"


# Description: Class `MessageRole` encapsulates related data and behavior for this module.
class MessageRole(str, PyEnum):
    """Supported message roles stored in the session transcript."""

    user = "user"
    assistant = "assistant"
    system = "system"


# Description: Class `Tenant` encapsulates related data and behavior for this module.
class Tenant(Base):
    """Logical tenant boundary for all users, sessions, and vector resources."""

    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="tenant")
    sessions = relationship("CoachingSession", back_populates="tenant")


# Description: Class `User` encapsulates related data and behavior for this module.
class User(Base):
    """Authenticated platform user synchronized from Keycloak claims."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keycloak_sub = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.client)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    coach_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant", back_populates="users")
    client_sessions = relationship(
        "CoachingSession", foreign_keys="CoachingSession.client_id", back_populates="client"
    )
    coach_sessions = relationship(
        "CoachingSession", foreign_keys="CoachingSession.coach_id", back_populates="coach"
    )


# Description: Class `CoachingSession` encapsulates related data and behavior for this module.
class CoachingSession(Base):
    """Persisted coaching conversation between one client and the AI assistant."""

    __tablename__ = "coaching_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    coach_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    status = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.active)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client = relationship("User", foreign_keys=[client_id], back_populates="client_sessions")
    coach = relationship("User", foreign_keys=[coach_id], back_populates="coach_sessions")
    tenant = relationship("Tenant", back_populates="sessions")
    messages = relationship("Message", back_populates="session", order_by="Message.created_at")


# Description: Class `Message` encapsulates related data and behavior for this module.
class Message(Base):
    """Single message in a coaching session transcript."""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("coaching_sessions.id"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("CoachingSession", back_populates="messages")


# Description: Class `CoachDocument` encapsulates related data and behavior for this module.
class CoachDocument(Base):
    """Original file bytes uploaded by a coach for a specific client.

    Stored separately from methodology documents (which live only in ChromaDB).
    is_active=False marks rows that have been superseded by a hard-replace upload.
    """

    __tablename__ = "coach_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(String(36), nullable=False, unique=True, index=True)  # matches ChromaDB metadata key
    coach_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    filename = Column(String(512), nullable=False)
    content_type = Column(String(128), nullable=False, default="application/octet-stream")
    file_bytes = Column(LargeBinary, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    coach = relationship("User", foreign_keys=[coach_id])
    client = relationship("User", foreign_keys=[client_id])
    tenant = relationship("Tenant")


class MethodologyDocument(Base):
    """Original file bytes for admin-uploaded coaching procedure documents.

    Raw bytes are stored here so admins can download originals and content
    remains recoverable after chunking. is_active=False marks rows
    superseded by a hard-replace upload.
    """

    __tablename__ = "methodology_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(String(36), nullable=False, unique=True, index=True)  # matches ChromaDB metadata key
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    filename = Column(String(512), nullable=False)
    content_type = Column(String(128), nullable=False, default="application/octet-stream")
    file_bytes = Column(LargeBinary, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    tenant = relationship("Tenant")
    uploader = relationship("User", foreign_keys=[uploaded_by])


class PromptTemplate(Base):
    """Admin-managed prompt templates stored in the database.

    Lists (guardrails, keywords) are stored as JSON text with is_json=True.
    updated_by is NULL for rows that were seeded by the Alembic migration.
    """

    __tablename__ = "prompt_templates"

    key = Column(String(100), primary_key=True)
    content = Column(Text, nullable=False)
    is_json = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
