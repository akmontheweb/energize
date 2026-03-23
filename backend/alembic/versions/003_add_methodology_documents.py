"""add methodology_documents table

Revision ID: 003_add_methodology_documents
Revises: 002_add_prompt_templates
Create Date: 2026-04-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_add_methodology_documents"
down_revision = "002_add_prompt_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "methodology_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("doc_id", sa.String(36), nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column(
            "content_type",
            sa.String(128),
            nullable=False,
            server_default="application/octet-stream",
        ),
        sa.Column("file_bytes", sa.LargeBinary, nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
    )
    op.create_unique_constraint(
        "uq_methodology_documents_doc_id", "methodology_documents", ["doc_id"]
    )
    op.create_index(
        "idx_methodology_documents_doc_id", "methodology_documents", ["doc_id"]
    )
    op.create_index(
        "idx_methodology_documents_tenant_id", "methodology_documents", ["tenant_id"]
    )
    op.create_index(
        "idx_methodology_documents_tenant_active",
        "methodology_documents",
        ["tenant_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("idx_methodology_documents_tenant_active", "methodology_documents")
    op.drop_index("idx_methodology_documents_tenant_id", "methodology_documents")
    op.drop_index("idx_methodology_documents_doc_id", "methodology_documents")
    op.drop_constraint(
        "uq_methodology_documents_doc_id", "methodology_documents"
    )
    op.drop_table("methodology_documents")
