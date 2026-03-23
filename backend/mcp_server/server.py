"""Energize Coaching MCP Server.

Exposes:
  Prompts    — all prompt templates from prompts.yaml (MCP prompt primitives)
  Tools      — all PostgreSQL operations (async) and ChromaDB operations (sync)

Run standalone:
    python -m mcp_server            # SSE server on MCP_PORT (default 9000)
    mcp dev backend/mcp_server/server.py   # MCP Inspector + hot-reload

External MCP clients (Claude Desktop, mcp CLI, langchain-mcp-adapters) connect to:
    http://<host>:9000/sse
"""
from mcp.server.fastmcp import FastMCP

import os

from mcp_server.resources import prompts as _prompts
from mcp_server.tools import pgvector as _pv
from mcp_server.tools import postgres as _pg

mcp = FastMCP(
    "energize-coaching",
    host="0.0.0.0",
    port=int(os.getenv("MCP_PORT", "9000")),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Prompts — prompt primitives
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.prompt()
async def coach_system_prompt() -> str:
    """Full coach system prompt including guardrails. Used as the LLM system context."""
    return await _prompts.get_coach_system_prompt()


@mcp.prompt()
async def intake_extraction(conversation: str) -> str:
    """Goal extraction prompt with the session conversation filled in."""
    return (await _prompts.get_intake_extraction_prompt()).format(conversation=conversation)


@mcp.prompt()
async def reflection_summary(goals: str, transcript: str) -> str:
    """Session reflection summary prompt with goals and transcript filled in."""
    return (await _prompts.get_reflection_summary_prompt()).format(goals=goals, transcript=transcript)


@mcp.prompt()
async def escalation_message() -> str:
    """Crisis escalation message displayed to users when escalation is triggered."""
    return await _prompts.get_escalation_message()


@mcp.prompt()
async def escalation_keywords() -> str:
    """Escalation trigger keywords as a JSON array."""
    return await _prompts.get_escalation_keywords_json()


# ═══════════════════════════════════════════════════════════════════════════════
# Tools — PostgreSQL
# ═══════════════════════════════════════════════════════════════════════════════

mcp.tool()(_pg.pg_get_or_create_tenant)

mcp.tool()(_pg.pg_get_user_by_sub)
mcp.tool()(_pg.pg_get_user_by_id)
mcp.tool()(_pg.pg_get_users_by_ids)
mcp.tool()(_pg.pg_upsert_user)
mcp.tool()(_pg.pg_list_users)
mcp.tool()(_pg.pg_assign_coach)

mcp.tool()(_pg.pg_get_session)
mcp.tool()(_pg.pg_get_session_with_messages)
mcp.tool()(_pg.pg_list_sessions)
mcp.tool()(_pg.pg_get_last_messages_for_sessions)
mcp.tool()(_pg.pg_create_session)
mcp.tool()(_pg.pg_update_session)
mcp.tool()(_pg.pg_delete_session)

mcp.tool()(_pg.pg_get_session_messages)
mcp.tool()(_pg.pg_append_message)

mcp.tool()(_pg.pg_save_coach_document)
mcp.tool()(_pg.pg_get_coach_document)
mcp.tool()(_pg.pg_archive_coach_document)
mcp.tool()(_pg.pg_list_active_coach_documents)


# ═══════════════════════════════════════════════════════════════════════════════
# Tools — pgvector
# ═══════════════════════════════════════════════════════════════════════════════

mcp.tool()(_pv.pgvector_query_methodology_docs)
mcp.tool()(_pv.pgvector_ingest_methodology_docs)
mcp.tool()(_pv.pgvector_list_methodology_docs)
mcp.tool()(_pv.pgvector_delete_methodology_doc)

mcp.tool()(_pv.pgvector_query_coach_docs)
mcp.tool()(_pv.pgvector_ingest_coach_docs)
mcp.tool()(_pv.pgvector_list_coach_docs)
mcp.tool()(_pv.pgvector_delete_coach_doc)
