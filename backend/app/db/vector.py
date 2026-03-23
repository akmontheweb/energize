import logging
from typing import List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

logger = logging.getLogger(__name__)


# Description: Function `get_chroma_client` implementation.
# Inputs: None
# Output: chromadb.HttpClient
# Exceptions: Propagates exceptions raised by internal operations.
def get_chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=settings.CHROMA_HOST,
        port=settings.CHROMA_PORT,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


# Description: Function `get_tenant_collection` implementation.
# Inputs: tenant_id, client
# Output: Varies by implementation
# Exceptions: Propagates exceptions raised by internal operations.
def get_tenant_collection(tenant_id: str, client: Optional[chromadb.HttpClient] = None):
    """Return (or create) a tenant-namespaced ChromaDB collection."""
    if client is None:
        client = get_chroma_client()
    collection_name = f"tenant_{tenant_id}_resources"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


# Description: Function `query_resources` implementation.
# Inputs: tenant_id, query_texts, n_results
# Output: List[str]
# Exceptions: Propagates exceptions raised by internal operations.
def query_resources(
    tenant_id: str,
    query_texts: List[str],
    n_results: int = 5,
) -> List[str]:
    """Query ChromaDB for coaching resources relevant to the query."""
    try:
        client = get_chroma_client()
        collection = get_tenant_collection(tenant_id, client)
        results = collection.query(
            query_texts=query_texts,
            n_results=n_results,
            include=["documents"],
        )
        docs = results.get("documents", [[]])[0]
        return docs
    except Exception:
        logger.exception(
            "Vector query failed tenant_id=%s n_results=%s query_count=%s",
            tenant_id,
            n_results,
            len(query_texts),
        )
        return []


# Description: Function `ingest_documents` implementation.
# Inputs: tenant_id, documents, ids, metadatas
# Output: None
# Exceptions: Propagates exceptions raised by internal operations.
def ingest_documents(
    tenant_id: str,
    documents: List[str],
    ids: List[str],
    metadatas: Optional[List[dict]] = None,
) -> None:
    """Ingest documents into a tenant-namespaced ChromaDB collection."""
    try:
        client = get_chroma_client()
        collection = get_tenant_collection(tenant_id, client)
        collection.upsert(
            documents=documents,
            ids=ids,
            metadatas=metadatas or [{} for _ in documents],
        )
    except Exception:
        logger.exception(
            "Vector ingestion failed tenant_id=%s document_count=%s id_count=%s",
            tenant_id,
            len(documents),
            len(ids),
        )
        raise


# Description: Function `list_documents` implementation.
# Inputs: tenant_id
# Output: List[dict]
# Exceptions: Propagates exceptions raised by internal operations.
def list_documents(tenant_id: str) -> List[dict]:
    """Return one entry per unique document (grouped by doc_id metadata key)."""
    try:
        client = get_chroma_client()
        collection = get_tenant_collection(tenant_id, client)
        result = collection.get(include=["metadatas"])
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
        logger.exception("Vector document listing failed tenant_id=%s", tenant_id)
        return []


# Description: Function `delete_document` implementation.
# Inputs: tenant_id, doc_id
# Output: bool
# Exceptions: Propagates exceptions raised by internal operations.
def delete_document(tenant_id: str, doc_id: str) -> bool:
    """Delete all chunks belonging to a document by its doc_id. Returns True if any were deleted."""
    try:
        client = get_chroma_client()
        collection = get_tenant_collection(tenant_id, client)
        result = collection.get(where={"doc_id": doc_id}, include=["metadatas"])
        ids_to_delete = result.get("ids", [])
        if not ids_to_delete:
            return False
        collection.delete(ids=ids_to_delete)
        return True
    except Exception:
        logger.exception("Vector document delete failed tenant_id=%s doc_id=%s", tenant_id, doc_id)
        return False


# =============================================================================
# Coach-conversation collection (separate from admin methodology docs)
# Collection name: tenant_{tenant_id}_coach_conversations
# =============================================================================

def get_coach_collection(tenant_id: str, client: Optional[chromadb.HttpClient] = None):
    """Return (or create) the tenant-namespaced coach-conversations ChromaDB collection."""
    if client is None:
        client = get_chroma_client()
    collection_name = f"tenant_{tenant_id}_coach_conversations"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def ingest_coach_documents(
    tenant_id: str,
    documents: List[str],
    ids: List[str],
    metadatas: Optional[List[dict]] = None,
) -> None:
    """Ingest coach-uploaded client-conversation chunks into the coach-conversations collection."""
    try:
        client = get_chroma_client()
        collection = get_coach_collection(tenant_id, client)
        collection.upsert(
            documents=documents,
            ids=ids,
            metadatas=metadatas or [{} for _ in documents],
        )
    except Exception:
        logger.exception(
            "Coach vector ingestion failed tenant_id=%s document_count=%s",
            tenant_id,
            len(documents),
        )
        raise


def query_coach_resources(
    tenant_id: str,
    client_id: str,
    query_texts: List[str],
    n_results: int = 5,
) -> List[str]:
    """Query coach-conversation docs in ChromaDB filtered to a specific client."""
    try:
        client = get_chroma_client()
        collection = get_coach_collection(tenant_id, client)
        results = collection.query(
            query_texts=query_texts,
            where={"client_id": client_id},
            n_results=n_results,
            include=["documents"],
        )
        docs = results.get("documents", [[]])[0]
        return docs
    except Exception:
        logger.exception(
            "Coach vector query failed tenant_id=%s client_id=%s n_results=%s",
            tenant_id,
            client_id,
            n_results,
        )
        return []


def list_coach_documents(
    tenant_id: str,
    coach_id: str,
    client_id: Optional[str] = None,
) -> List[dict]:
    """Return one entry per unique active coach-conversation document."""
    try:
        client = get_chroma_client()
        collection = get_coach_collection(tenant_id, client)
        where_filter: dict = {"coach_id": coach_id}
        if client_id:
            where_filter = {"$and": [{"coach_id": coach_id}, {"client_id": client_id}]}
        result = collection.get(where=where_filter, include=["metadatas"])
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
            "Coach vector document listing failed tenant_id=%s coach_id=%s",
            tenant_id,
            coach_id,
        )
        return []


def delete_coach_document(tenant_id: str, doc_id: str) -> bool:
    """Delete all chunks of a coach-conversation document by doc_id. Returns True if any deleted."""
    try:
        client = get_chroma_client()
        collection = get_coach_collection(tenant_id, client)
        result = collection.get(where={"doc_id": doc_id}, include=["metadatas"])
        ids_to_delete = result.get("ids", [])
        if not ids_to_delete:
            return False
        collection.delete(ids=ids_to_delete)
        return True
    except Exception:
        logger.exception(
            "Coach vector document delete failed tenant_id=%s doc_id=%s",
            tenant_id,
            doc_id,
        )
        return False
