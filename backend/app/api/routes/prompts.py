"""Admin-only endpoints for reading and updating prompt templates.

GET  /api/v1/prompts   — return all prompt templates as structured JSON
PUT  /api/v1/prompts   — overwrite all prompt templates; persists to the database

Only users with the ``admin`` role can access these endpoints.
"""
import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api.deps import get_current_user, get_db
from app.db.models import PromptTemplate, User, UserRole

router = APIRouter(prefix="/prompts", tags=["prompts"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class PromptsConfig(BaseModel):
    coach_system_prompt: str
    guardrails_do: List[str]
    guardrails_do_not: List[str]
    intake_extraction_prompt: str
    reflection_summary_prompt: str
    escalation_message: str
    escalation_keywords: List[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_admin(current_user: User) -> None:
    if current_user.role != UserRole.admin:
        logger.warning(
            "Rejected admin-only prompt operation requester_id=%s role=%s",
            current_user.id,
            current_user.role.value,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


async def _load_config(db: AsyncSession) -> PromptsConfig:
    result = await db.execute(select(PromptTemplate))
    rows: dict[str, PromptTemplate] = {r.key: r for r in result.scalars().all()}

    def text(key: str) -> str:
        row = rows.get(key)
        return row.content if row else ""

    def lst(key: str) -> List[str]:
        row = rows.get(key)
        if not row:
            return []
        return json.loads(row.content)

    return PromptsConfig(
        coach_system_prompt=text("coach_system_prompt"),
        guardrails_do=lst("guardrails_do"),
        guardrails_do_not=lst("guardrails_do_not"),
        intake_extraction_prompt=text("intake_extraction_prompt"),
        reflection_summary_prompt=text("reflection_summary_prompt"),
        escalation_message=text("escalation_message"),
        escalation_keywords=lst("escalation_keywords"),
    )


async def _upsert_all(db: AsyncSession, config: PromptsConfig, updated_by_id) -> None:
    rows = [
        {"key": "coach_system_prompt",       "content": config.coach_system_prompt,                  "is_json": False},
        {"key": "guardrails_do",             "content": json.dumps(config.guardrails_do),             "is_json": True},
        {"key": "guardrails_do_not",         "content": json.dumps(config.guardrails_do_not),         "is_json": True},
        {"key": "intake_extraction_prompt",  "content": config.intake_extraction_prompt,              "is_json": False},
        {"key": "reflection_summary_prompt", "content": config.reflection_summary_prompt,             "is_json": False},
        {"key": "escalation_message",        "content": config.escalation_message,                    "is_json": False},
        {"key": "escalation_keywords",       "content": json.dumps(config.escalation_keywords),       "is_json": True},
    ]
    for row in rows:
        stmt = (
            pg_insert(PromptTemplate)
            .values(
                key=row["key"],
                content=row["content"],
                is_json=row["is_json"],
                updated_by=updated_by_id,
            )
            .on_conflict_do_update(
                index_elements=["key"],
                set_={
                    "content": row["content"],
                    "is_json": row["is_json"],
                    "updated_at": func.now(),
                    "updated_by": updated_by_id,
                },
            )
        )
        await db.execute(stmt)
    await db.flush()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=PromptsConfig)
async def get_prompts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PromptsConfig:
    """Admin only: return all prompt templates."""
    _require_admin(current_user)
    config = await _load_config(db)
    logger.info("Returned prompt templates admin_id=%s", current_user.id)
    return config


@router.put("", response_model=PromptsConfig)
async def update_prompts(
    payload: PromptsConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PromptsConfig:
    """Admin only: overwrite all prompt templates."""
    _require_admin(current_user)
    await _upsert_all(db, payload, current_user.id)
    config = await _load_config(db)
    logger.info("Updated prompt templates admin_id=%s", current_user.id)
    return config
