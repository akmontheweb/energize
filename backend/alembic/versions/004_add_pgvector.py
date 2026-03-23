"""Add pgvector extension and document chunk tables.

Replaces ChromaDB as the vector store.  Chunk embeddings are stored in two
new tables that mirror the existing coach_documents / methodology_documents
tables (which hold raw file bytes and metadata).

The vector dimension defaults to 1536 (OpenAI text-embedding-3-small / Azure).
Override EMBEDDING_DIMENSIONS in .env before running this migration if you use
a different provider:
  google_genai  → 768
  mistralai     → 1024
  openai        → 1536  (default)

Revision ID: 004
Revises    : 003
"""
from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# ── revision identifiers ──────────────────────────────────────────────────────
revision = "004"
down_revision = "003_add_methodology_documents"
branch_labels = None
depends_on = None

# Read dimension from env so the column matches whatever provider is configured.
_DIMS = int(os.environ.get("EMBEDDING_DIMENSIONS", "1536"))


def upgrade() -> None:
    # Enable the pgvector extension (idempotent).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── methodology_document_chunks ───────────────────────────────────────────
    op.create_table(
        "methodology_document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("doc_id", sa.String(36), sa.ForeignKey("methodology_documents.doc_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "embedding",
            sa.Text,  # placeholder; replaced by the real vector type below
            nullable=True,
        ),
        sa.Column("metadata_", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    # Replace the placeholder Text column with the actual vector type.
    op.execute(f"ALTER TABLE methodology_document_chunks DROP COLUMN embedding")
    op.execute(f"ALTER TABLE methodology_document_chunks ADD COLUMN embedding vector({_DIMS})")

    # Indexes
    op.create_index("ix_mdc_tenant_doc", "methodology_document_chunks", ["tenant_id", "doc_id"])
    op.execute(
        "CREATE INDEX ix_mdc_embedding ON methodology_document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # ── coach_document_chunks ─────────────────────────────────────────────────
    op.create_table(
        "coach_document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("doc_id", sa.String(36), sa.ForeignKey("coach_documents.doc_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("coach_id", sa.String(36), nullable=False),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "embedding",
            sa.Text,  # placeholder
            nullable=True,
        ),
        sa.Column("metadata_", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.execute("ALTER TABLE coach_document_chunks DROP COLUMN embedding")
    op.execute(f"ALTER TABLE coach_document_chunks ADD COLUMN embedding vector({_DIMS})")

    # Indexes
    op.create_index("ix_cdc_tenant_doc", "coach_document_chunks", ["tenant_id", "doc_id"])
    op.create_index("ix_cdc_tenant_client", "coach_document_chunks", ["tenant_id", "client_id"])
    op.execute(
        "CREATE INDEX ix_cdc_embedding ON coach_document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cdc_embedding")
    op.execute("DROP INDEX IF EXISTS ix_mdc_embedding")
    op.drop_index("ix_cdc_tenant_client", table_name="coach_document_chunks")
    op.drop_index("ix_cdc_tenant_doc", table_name="coach_document_chunks")
    op.drop_table("coach_document_chunks")
    op.drop_index("ix_mdc_tenant_doc", table_name="methodology_document_chunks")
    op.drop_table("methodology_document_chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")
