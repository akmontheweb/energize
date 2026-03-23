"""pgvector tools for the MCP server.

Drop-in replacement for mcp_server/tools/chroma.py.  All public functions
expose the same signatures so call sites in routes and agent nodes only
need an import swap.

Vectors are stored in two PostgreSQL tables (created by migration 004):
  methodology_document_chunks  — admin-uploaded methodology / resource docs
  coach_document_chunks        — coach-uploaded client conversation docs

Embeddings are generated via the provider configured in settings
(LLM_PROVIDER / EMBEDDING_MODEL) using the get_embeddings() factory from
app.core.llm, keeping the embedding model consistent with the LLM provider.

All functions are intentionally synchronous (mirrors the original chroma.py
contract).  asyncpg is used under the hood via a short-lived sync wrapper so
we don't need a separate sync engine.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import asyncpg

from app.core.config import settings
from app.core.llm import get_embeddings

logger = logging.getLogger(__name__)

# ── Lazy embedding model ──────────────────────────────────────────────────────
_embeddings = None


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = get_embeddings()
    return _embeddings


def _embed(text: str) -> list[float]:
    """Return the embedding vector for *text* using the configured provider."""
    return _get_embeddings().embed_query(text)


# ── Sync DB helper ────────────────────────────────────────────────────────────

def _dsn() -> str:
    """Return a plain (non-asyncpg) DSN for synchronous connections."""
    url = settings.DATABASE_URL
    # SQLAlchemy async DSN uses postgresql+asyncpg:// — strip the driver part.
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _run(coro):
    """Run an asyncpg coroutine synchronously inside a new event loop."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)


async def _execute(sql: str, *args):
    conn = await asyncpg.connect(_dsn())
    try:
        return await conn.execute(sql, *args)
    finally:
        await conn.close()


async def _fetch(sql: str, *args) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(_dsn())
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


async def _fetchval(sql: str, *args):
    conn = await asyncpg.connect(_dsn())
    try:
        return await conn.fetchval(sql, *args)
    finally:
        await conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Admin methodology documents
# ═══════════════════════════════════════════════════════════════════════════════

def pgvector_query_methodology_docs(
    tenant_id: str,
    query: str,
    n_results: int = 5,
) -> list[str]:
    """Semantic similarity search across admin-uploaded methodology documents."""
    try:
        embedding = _embed(query)
        vec = f"[{','.join(str(v) for v in embedding)}]"
        rows = _run(_fetch(
            """
            SELECT content
            FROM methodology_document_chunks
            WHERE tenant_id = $1
            ORDER BY embedding <=> $2::vector
            LIMIT $3
            """,
            tenant_id,
            vec,
            n_results,
        ))
        return [r["content"] for r in rows]
    except Exception:
        logger.exception("Methodology doc query failed tenant_id=%s", tenant_id)
        return []


def pgvector_ingest_methodology_docs(
    tenant_id: str,
    documents: list[str],
    ids: list[str],
    metadatas: Optional[list[dict]] = None,
) -> None:
    """Upsert admin methodology document chunks into pgvector."""
    try:
        metas = metadatas or [{} for _ in documents]

        async def _upsert():
            conn = await asyncpg.connect(_dsn())
            try:
                for chunk_id, content, meta in zip(ids, documents, metas):
                    embedding = _embed(content)
                    vec = f"[{','.join(str(v) for v in embedding)}]"
                    await conn.execute(
                        """
                        INSERT INTO methodology_document_chunks
                            (id, doc_id, tenant_id, chunk_index, content, embedding, metadata_)
                        VALUES (
                            $1::uuid,
                            $2,
                            $3,
                            $4,
                            $5,
                            $6::vector,
                            $7::jsonb
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            content    = EXCLUDED.content,
                            embedding  = EXCLUDED.embedding,
                            metadata_  = EXCLUDED.metadata_
                        """,
                        chunk_id,
                        meta.get("doc_id", chunk_id),
                        tenant_id,
                        int(meta.get("chunk_index", 0)),
                        content,
                        vec,
                        json.dumps(meta),
                    )
            finally:
                await conn.close()

        _run(_upsert())
    except Exception:
        logger.exception(
            "Methodology doc ingestion failed tenant_id=%s document_count=%s",
            tenant_id,
            len(documents),
        )
        raise


def pgvector_list_methodology_docs(tenant_id: str) -> list[dict]:
    """Return one entry per unique methodology document (grouped by doc_id)."""
    try:
        rows = _run(_fetch(
            """
            SELECT
                metadata_->>'doc_id'       AS doc_id,
                metadata_->>'filename'     AS filename,
                metadata_->>'uploaded_at'  AS uploaded_at,
                COUNT(*)                   AS chunk_count
            FROM methodology_document_chunks
            WHERE tenant_id = $1
              AND metadata_->>'doc_id' IS NOT NULL
            GROUP BY
                metadata_->>'doc_id',
                metadata_->>'filename',
                metadata_->>'uploaded_at'
            """,
            tenant_id,
        ))
        return [
            {
                "doc_id": r["doc_id"],
                "filename": r["filename"] or "unknown",
                "chunk_count": r["chunk_count"],
                "uploaded_at": r["uploaded_at"],
            }
            for r in rows
        ]
    except Exception:
        logger.exception("Methodology doc list failed tenant_id=%s", tenant_id)
        return []


def pgvector_delete_methodology_doc(tenant_id: str, doc_id: str) -> bool:
    """Delete all chunks of a methodology document by doc_id. Returns True if any deleted."""
    try:
        result = _run(_execute(
            "DELETE FROM methodology_document_chunks WHERE tenant_id = $1 AND doc_id = $2",
            tenant_id,
            doc_id,
        ))
        # asyncpg returns 'DELETE N' as a string
        deleted = int(result.split()[-1]) if result else 0
        return deleted > 0
    except Exception:
        logger.exception(
            "Methodology doc delete failed tenant_id=%s doc_id=%s", tenant_id, doc_id
        )
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Coach-conversation documents
# ═══════════════════════════════════════════════════════════════════════════════

def pgvector_query_coach_docs(
    tenant_id: str,
    client_id: str,
    query: str,
    n_results: int = 5,
) -> list[str]:
    """Semantic search across coach-uploaded client-conversation documents."""
    try:
        embedding = _embed(query)
        vec = f"[{','.join(str(v) for v in embedding)}]"
        rows = _run(_fetch(
            """
            SELECT content
            FROM coach_document_chunks
            WHERE tenant_id = $1
              AND client_id = $2
            ORDER BY embedding <=> $3::vector
            LIMIT $4
            """,
            tenant_id,
            client_id,
            vec,
            n_results,
        ))
        return [r["content"] for r in rows]
    except Exception:
        logger.exception(
            "Coach doc query failed tenant_id=%s client_id=%s", tenant_id, client_id
        )
        return []


def pgvector_ingest_coach_docs(
    tenant_id: str,
    documents: list[str],
    ids: list[str],
    metadatas: Optional[list[dict]] = None,
) -> None:
    """Upsert coach-uploaded document chunks into pgvector."""
    try:
        metas = metadatas or [{} for _ in documents]

        async def _upsert():
            conn = await asyncpg.connect(_dsn())
            try:
                for chunk_id, content, meta in zip(ids, documents, metas):
                    embedding = _embed(content)
                    vec = f"[{','.join(str(v) for v in embedding)}]"
                    await conn.execute(
                        """
                        INSERT INTO coach_document_chunks
                            (id, doc_id, tenant_id, coach_id, client_id,
                             chunk_index, content, embedding, metadata_)
                        VALUES (
                            $1::uuid,
                            $2,
                            $3,
                            $4,
                            $5,
                            $6,
                            $7,
                            $8::vector,
                            $9::jsonb
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            content    = EXCLUDED.content,
                            embedding  = EXCLUDED.embedding,
                            metadata_  = EXCLUDED.metadata_
                        """,
                        chunk_id,
                        meta.get("doc_id", chunk_id),
                        tenant_id,
                        meta.get("coach_id", ""),
                        meta.get("client_id", ""),
                        int(meta.get("chunk_index", 0)),
                        content,
                        vec,
                        json.dumps(meta),
                    )
            finally:
                await conn.close()

        _run(_upsert())
    except Exception:
        logger.exception(
            "Coach doc ingestion failed tenant_id=%s document_count=%s", tenant_id, len(documents)
        )
        raise


def pgvector_list_coach_docs(
    tenant_id: str,
    coach_id: str,
    client_id: Optional[str] = None,
) -> list[dict]:
    """Return one entry per unique coach-conversation document."""
    try:
        if client_id:
            rows = _run(_fetch(
                """
                SELECT
                    metadata_->>'doc_id'      AS doc_id,
                    metadata_->>'filename'    AS filename,
                    client_id,
                    metadata_->>'uploaded_at' AS uploaded_at,
                    COUNT(*)                  AS chunk_count
                FROM coach_document_chunks
                WHERE tenant_id = $1
                  AND coach_id  = $2
                  AND client_id = $3
                  AND metadata_->>'doc_id' IS NOT NULL
                GROUP BY
                    metadata_->>'doc_id',
                    metadata_->>'filename',
                    client_id,
                    metadata_->>'uploaded_at'
                """,
                tenant_id,
                coach_id,
                client_id,
            ))
        else:
            rows = _run(_fetch(
                """
                SELECT
                    metadata_->>'doc_id'      AS doc_id,
                    metadata_->>'filename'    AS filename,
                    client_id,
                    metadata_->>'uploaded_at' AS uploaded_at,
                    COUNT(*)                  AS chunk_count
                FROM coach_document_chunks
                WHERE tenant_id = $1
                  AND coach_id  = $2
                  AND metadata_->>'doc_id' IS NOT NULL
                GROUP BY
                    metadata_->>'doc_id',
                    metadata_->>'filename',
                    client_id,
                    metadata_->>'uploaded_at'
                """,
                tenant_id,
                coach_id,
            ))

        return [
            {
                "doc_id": r["doc_id"],
                "filename": r["filename"] or "unknown",
                "client_id": r["client_id"] or "",
                "chunk_count": r["chunk_count"],
                "uploaded_at": r["uploaded_at"],
            }
            for r in rows
        ]
    except Exception:
        logger.exception(
            "Coach doc list failed tenant_id=%s coach_id=%s", tenant_id, coach_id
        )
        return []


def pgvector_delete_coach_doc(tenant_id: str, doc_id: str) -> bool:
    """Delete all chunks of a coach document by doc_id. Returns True if any deleted."""
    try:
        result = _run(_execute(
            "DELETE FROM coach_document_chunks WHERE tenant_id = $1 AND doc_id = $2",
            tenant_id,
            doc_id,
        ))
        deleted = int(result.split()[-1]) if result else 0
        return deleted > 0
    except Exception:
        logger.exception(
            "Coach doc delete failed tenant_id=%s doc_id=%s", tenant_id, doc_id
        )
        return False
