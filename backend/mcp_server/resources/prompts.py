"""Prompt access functions for the MCP server and agent nodes.

Prompts are stored in the ``prompt_templates`` PostgreSQL table and fetched
fresh on every call so admin edits via the UI take effect immediately without
restarting the server.
"""
import json
import logging
from typing import Any

from sqlalchemy.future import select

from app.db.database import AsyncSessionLocal
from app.db.models import PromptTemplate

logger = logging.getLogger(__name__)


async def _fetch(key: str) -> str:
    """Return the raw content string for a prompt key. Raises RuntimeError if missing."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PromptTemplate).where(PromptTemplate.key == key)
        )
        row = result.scalar_one_or_none()
    if row is None:
        raise RuntimeError(f"Prompt template '{key}' not found in database")
    return row.content


async def _fetch_json(key: str) -> list:
    """Fetch and JSON-parse a list-type prompt row."""
    return json.loads(await _fetch(key))


async def get_coach_system_prompt() -> str:
    """Full coach system prompt including all guardrails."""
    base = (await _fetch("coach_system_prompt")).strip()
    do_items = await _fetch_json("guardrails_do")
    dont_items = await _fetch_json("guardrails_do_not")
    if not do_items and not dont_items:
        return base
    lines = [base, "\n\n## Guardrails"]
    if do_items:
        lines.append("\nYou MUST always:")
        lines.extend(f"- {item}" for item in do_items)
    if dont_items:
        lines.append("\nYou MUST NEVER:")
        lines.extend(f"- {item}" for item in dont_items)
    return "\n".join(lines)


async def get_intake_extraction_prompt() -> str:
    """Prompt template for extracting client goals. Contains ``{conversation}`` placeholder."""
    return (await _fetch("intake_extraction_prompt")).strip()


async def get_reflection_summary_prompt() -> str:
    """Prompt template for session reflection. Contains ``{goals}`` and ``{transcript}`` placeholders."""
    return (await _fetch("reflection_summary_prompt")).strip()


async def get_escalation_message() -> str:
    """Crisis escalation message displayed when a trigger keyword is detected."""
    return (await _fetch("escalation_message")).strip()


async def get_escalation_keywords() -> list[str]:
    """List of keywords that trigger escalation routing."""
    return await _fetch_json("escalation_keywords")


async def get_escalation_keywords_json() -> str:
    """Escalation keywords as a raw JSON array string (used by MCP prompt primitives)."""
    return await _fetch("escalation_keywords")


def get_escalation_keywords_json() -> str:
    """Escalation keywords as a JSON-serialised string (for the MCP resource endpoint)."""
    return json.dumps(get_escalation_keywords())
