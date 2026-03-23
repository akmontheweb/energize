"""ChromaDB tools for the MCP server.

Replaces backend/app/db/vector.py as the single source of truth for all
ChromaDB access.  All public functions are:
  - Registered as MCP tools in mcp_server/server.py (for external protocol access)
  - Imported directly by REST routes and agent nodes (same-process Python call)

The ChromaDB HttpClient is synchronous; these functions are intentionally sync.
"""
import logging
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────── internal helpers ──────────────────────────────────

def _get_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=settings.CHROMA_HOST,
        port=settings.CHROMA_PORT,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _get_collection(tenant_id: str, client: Optional[chromadb.HttpClient] = None):
    """Return (or create) the tenant methodology-docs ChromaDB collection."""
    if client is None:
        client = _get_client()
    return client.get_or_create_collection(
        name=f"tenant_{tenant_id}_resources",
        metadata={"hnsw:space": "cosine"},
    )


def _get_coach_collection(tenant_id: str, client: Optional[chromadb.HttpClient] = None):
    """Return (or create) the tenant coach-conversations ChromaDB collection."""
    if client is None:
        client = _get_client()
    return client.get_or_create_collection(
        name=f"tenant_{tenant_id}_coach_conversations",
        metadata={"hnsw:space": "cosine"},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Admin methodology documents  (collection: tenant_{id}_resources)
# ═══════════════════════════════════════════════════════════════════════════════

def chroma_query_methodology_docs(
    tenant_id: str,
    query: str,
    n_results: int = 5,
) -> list[str]:
    """Semantic similarity search across admin-uploaded methodology documents."""
    try:
        col = _get_collection(tenant_id)
        available = len(col.get(include=[]).get("ids") or [])
        if available == 0:
            return []
        results = col.query(
            query_texts=[query],
            n_results=min(n_results, available),
            include=["documents"],
        )
        return results.get("documents", [[]])[0]
    except Exception:
        logger.exception("Methodology doc query failed tenant_id=%s", tenant_id)
        return []


def chroma_ingest_methodology_docs(
    tenant_id: str,
    documents: list[str],
    ids: list[str],
    metadatas: Optional[list[dict]] = None,
) -> None:
    """Upsert admin methodology document chunks into ChromaDB."""
    try:
        col = _get_collection(tenant_id)
        col.upsert(
            documents=documents,
            ids=ids,
            metadatas=metadatas or [{} for _ in documents],
        )
    except Exception:
        logger.exception(
            "Methodology doc ingestion failed tenant_id=%s document_count=%s",
            tenant_id,
            len(documents),
        )
        raise


def chroma_list_methodology_docs(tenant_id: str) -> list[dict]:
    """Return one entry per unique methodology document (grouped by doc_id metadata key)."""
    try:
        col = _get_collection(tenant_id)
        result = col.get(include=["metadatas"])
        seen: dict = {}
        for meta in (result.get("metadatas") or []):
            if not meta:
                continue
            doc_id = meta.get("doc_id")
            if not doc_id:
                continue
            if doc_id not in seen:
                seen[doc_id] = {
                    "doc_id": doc_id,
                    "filename": meta.get("filename", "unknown"),
                    "chunk_count": 1,
                    "uploaded_at": meta.get("uploaded_at"),
                }
            else:
                seen[doc_id]["chunk_count"] += 1
        return list(seen.values())
    except Exception:
        logger.exception("Methodology doc list failed tenant_id=%s", tenant_id)
        return []


def chroma_delete_methodology_doc(tenant_id: str, doc_id: str) -> bool:
    """Delete all chunks of a methodology document by doc_id. Returns True if any deleted."""
    try:
        col = _get_collection(tenant_id)
        result = col.get(where={"doc_id": doc_id}, include=["metadatas"])
        ids_to_delete = result.get("ids", [])
        if not ids_to_delete:
            return False
        col.delete(ids=ids_to_delete)
        return True
    except Exception:
        logger.exception(
            "Methodology doc delete failed tenant_id=%s doc_id=%s", tenant_id, doc_id
        )
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Coach-conversation documents  (collection: tenant_{id}_coach_conversations)
# ═══════════════════════════════════════════════════════════════════════════════

def chroma_query_coach_docs(
    tenant_id: str,
    client_id: str,
    query: str,
    n_results: int = 5,
) -> list[str]:
    """Semantic search across coach-uploaded client-conversation documents."""
    try:
        col = _get_coach_collection(tenant_id)
        available = len(
            col.get(where={"client_id": client_id}, include=[]).get("ids") or []
        )
        if available == 0:
            return []
        results = col.query(
            query_texts=[query],
            where={"client_id": client_id},
            n_results=min(n_results, available),
            include=["documents"],
        )
        return results.get("documents", [[]])[0]
    except Exception:
        logger.exception(
            "Coach doc query failed tenant_id=%s client_id=%s", tenant_id, client_id
        )
        return []


def chroma_ingest_coach_docs(
    tenant_id: str,
    documents: list[str],
    ids: list[str],
    metadatas: Optional[list[dict]] = None,
) -> None:
    """Upsert coach-uploaded document chunks into the coach-conversations collection."""
    try:
        col = _get_coach_collection(tenant_id)
        col.upsert(
            documents=documents,
            ids=ids,
            metadatas=metadatas or [{} for _ in documents],
        )
    except Exception:
        logger.exception(
            "Coach doc ingestion failed tenant_id=%s document_count=%s", tenant_id, len(documents)
        )
        raise


def chroma_list_coach_docs(
    tenant_id: str,
    coach_id: str,
    client_id: Optional[str] = None,
) -> list[dict]:
    """Return one entry per unique coach-conversation document."""
    try:
        col = _get_coach_collection(tenant_id)
        where_filter: dict = {"coach_id": coach_id}
        if client_id:
            where_filter = {"$and": [{"coach_id": coach_id}, {"client_id": client_id}]}
        result = col.get(where=where_filter, include=["metadatas"])
        seen: dict = {}
        for meta in (result.get("metadatas") or []):
            if not meta:
                continue
            doc_id = meta.get("doc_id")
            if not doc_id:
                continue
            if doc_id not in seen:
                seen[doc_id] = {
                    "doc_id": doc_id,
                    "filename": meta.get("filename", "unknown"),
                    "client_id": meta.get("client_id", ""),
                    "chunk_count": 1,
                    "uploaded_at": meta.get("uploaded_at"),
                }
            else:
                seen[doc_id]["chunk_count"] += 1
        return list(seen.values())
    except Exception:
        logger.exception(
            "Coach doc list failed tenant_id=%s coach_id=%s", tenant_id, coach_id
        )
        return []


def chroma_delete_coach_doc(tenant_id: str, doc_id: str) -> bool:
    """Delete all chunks of a coach-conversation document. Returns True if any deleted."""
    try:
        col = _get_coach_collection(tenant_id)
        result = col.get(where={"doc_id": doc_id}, include=["metadatas"])
        ids_to_delete = result.get("ids", [])
        if not ids_to_delete:
            return False
        col.delete(ids=ids_to_delete)
        return True
    except Exception:
        logger.exception(
            "Coach doc delete failed tenant_id=%s doc_id=%s", tenant_id, doc_id
        )
        return False
