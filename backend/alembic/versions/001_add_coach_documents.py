"""add coach_documents table

Revision ID: 001_add_coach_documents
Revises:
Create Date: 2026-03-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001_add_coach_documents"
down_revision = "000_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coach_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("doc_id", sa.String(36), nullable=False),
        sa.Column("coach_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False, server_default="application/octet-stream"),
        sa.Column("file_bytes", sa.LargeBinary, nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
    )
    op.create_unique_constraint("uq_coach_documents_doc_id", "coach_documents", ["doc_id"])
    op.create_index("idx_coach_documents_doc_id", "coach_documents", ["doc_id"])
    op.create_index("idx_coach_documents_coach_id", "coach_documents", ["coach_id"])
    op.create_index("idx_coach_documents_client_id", "coach_documents", ["client_id"])
    op.create_index("idx_coach_documents_tenant_id", "coach_documents", ["tenant_id"])
    op.create_index(
        "idx_coach_documents_coach_client_active",
        "coach_documents",
        ["coach_id", "client_id", "tenant_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("idx_coach_documents_coach_client_active", "coach_documents")
    op.drop_index("idx_coach_documents_tenant_id", "coach_documents")
    op.drop_index("idx_coach_documents_client_id", "coach_documents")
    op.drop_index("idx_coach_documents_coach_id", "coach_documents")
    op.drop_index("idx_coach_documents_doc_id", "coach_documents")
    op.drop_constraint("uq_coach_documents_doc_id", "coach_documents")
    op.drop_table("coach_documents")
