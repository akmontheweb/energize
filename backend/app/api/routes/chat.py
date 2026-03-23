import json
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from langchain_core.messages import HumanMessage

from app.core.security import verify_token
from app.core.telemetry import get_meter
from app.agents.graph import coaching_graph
from app.agents.state import CoachingState
from mcp_server.tools.postgres import (
    pg_get_user_by_sub,
    pg_get_user_by_id,
    pg_get_session,
    pg_get_session_messages,
    pg_append_message,
    pg_update_session,
)

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)

_meter = get_meter(__name__)
_active_sessions = _meter.create_up_down_counter(
    name="energize.coaching.sessions.active",
    description="Number of currently active WebSocket coaching sessions",
)


# Description: Function `websocket_chat` implementation.
# Inputs: websocket, session_id, token
# Output: Varies by implementation
# Exceptions: Propagates exceptions raised by internal operations.
@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: UUID,
    token: str = Query(...),
):
    await websocket.accept()
    logger.info("WebSocket connection accepted session_id=%s", session_id)

    # ── Validate JWT ──────────────────────────────────────────────────────────
    try:
        token_data = await verify_token(token)
    except Exception:
        logger.warning(
            "Rejected websocket connection session_id=%s reason=invalid_token", session_id
        )
        await websocket.send_json({"error": "Unauthorized"})
        await websocket.close(code=4001)
        return

    tenant_id = token_data["tenant_id"]
    user_sub = token_data["sub"]

    # ── Load user via MCP tool ────────────────────────────────────────────────
    user = await pg_get_user_by_sub(user_sub)
    if not user:
        logger.warning(
            "Rejected websocket connection session_id=%s sub=%s reason=user_not_found",
            session_id,
            user_sub,
        )
        await websocket.send_json({"error": "User not found"})
        await websocket.close(code=4004)
        return

    # ── Load session via MCP tool ─────────────────────────────────────────────
    coaching_session = await pg_get_session(str(session_id))
    if not coaching_session:
        logger.warning(
            "Rejected websocket connection session_id=%s user_id=%s reason=session_not_found",
            session_id,
            user["id"],
        )
        await websocket.send_json({"error": "Session not found"})
        await websocket.close(code=4004)
        return

    # ── Tenant guard ──────────────────────────────────────────────────────────
    if coaching_session["tenant_id"] != user["tenant_id"]:
        logger.warning(
            "Rejected websocket connection session_id=%s user_id=%s reason=tenant_mismatch",
            session_id,
            user["id"],
        )
        await websocket.send_json({"error": "Forbidden"})
        await websocket.close(code=4003)
        return

    # ── Role-based access guards ──────────────────────────────────────────────
    if user["role"] == "client" and coaching_session["client_id"] != user["id"]:
        logger.warning(
            "Rejected websocket connection session_id=%s user_id=%s reason=client_not_owner",
            session_id,
            user["id"],
        )
        await websocket.send_json({"error": "Forbidden"})
        await websocket.close(code=4003)
        return

    if user["role"] == "coach":
        session_client = await pg_get_user_by_id(coaching_session["client_id"])
        assigned_to_coach = bool(
            session_client and session_client.get("coach_id") == user["id"]
        )
        if not assigned_to_coach:
            logger.warning(
                "Rejected websocket connection session_id=%s coach_id=%s reason=coach_not_assigned",
                session_id,
                user["id"],
            )
            await websocket.send_json({"error": "Forbidden"})
            await websocket.close(code=4003)
            return

    logger.info(
        "WebSocket chat authorized session_id=%s user_id=%s role=%s tenant_id=%s",
        session_id,
        user["id"],
        user["role"],
        tenant_id,
    )
    _active_sessions.add(1, {"tenant_id": tenant_id})

    # ── Load existing messages for context ────────────────────────────────────
    existing_messages = await pg_get_session_messages(str(session_id))
    langchain_messages = [
        HumanMessage(content=m["content"])
        for m in existing_messages
        if m["role"] == "user"
    ]

    client_goals: list = []
    phase = "intake" if not langchain_messages else "coaching"

    try:
        while True:
            # Receive user message
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                user_text = data.get("message", raw)
            except json.JSONDecodeError:
                user_text = raw

            if not user_text.strip():
                continue

            # Check for end-session signal
            if user_text.strip().lower() in ["/end", "/reflect"]:
                phase = "reflection"

            # Persist user message via MCP tool
            await pg_append_message(str(session_id), "user", user_text)

            # Build LangGraph state
            new_human_message = HumanMessage(content=user_text)
            state: CoachingState = {
                "messages": langchain_messages + [new_human_message],
                "session_id": str(session_id),
                "tenant_id": tenant_id,
                "client_id": coaching_session["client_id"],
                "client_goals": client_goals,
                "phase": phase,
                "retrieved_resources": [],
                "needs_escalation": False,
            }

            config = {"configurable": {"thread_id": str(session_id)}}

            # Run the coaching graph
            result = await coaching_graph.ainvoke(state, config=config)

            # Extract the latest assistant response
            assistant_content = ""
            for msg in reversed(result.get("messages", [])):
                if hasattr(msg, "type") and msg.type == "ai":
                    assistant_content = msg.content
                    break

            if not assistant_content:
                assistant_content = "I'm here to support you. Could you tell me more?"

            # Update in-memory state for next iteration
            client_goals = result.get("client_goals", client_goals)
            phase = result.get("phase", "coaching")
            langchain_messages = result.get("messages", langchain_messages)

            # Persist assistant response via MCP tool
            await pg_append_message(
                str(session_id), "assistant", assistant_content, {"phase": phase}
            )

            # Update session status when escalated or reflected
            if result.get("needs_escalation") or phase == "escalated":
                await pg_update_session(str(session_id), status="escalated")
            elif phase == "reflection":
                await pg_update_session(str(session_id), status="completed")

            logger.info(
                "Processed chat turn session_id=%s user_id=%s phase=%s goals=%s",
                session_id,
                user["id"],
                phase,
                len(client_goals),
            )

            await websocket.send_json({
                "type": "message",
                "role": "assistant",
                "content": assistant_content,
                "phase": phase,
            })

    except WebSocketDisconnect:
        logger.info(
            "WebSocket disconnected session_id=%s user_id=%s", session_id, user["id"]
        )
        _active_sessions.add(-1, {"tenant_id": tenant_id})
    except Exception as e:
        logger.exception(
            "WebSocket chat processing failed session_id=%s user_id=%s tenant_id=%s",
            session_id,
            user["id"],
            tenant_id,
        )
        _active_sessions.add(-1, {"tenant_id": tenant_id})
        await websocket.send_json({
            "type": "message",
            "role": "assistant",
            "content": "I could not generate a response right now. Please try again in a moment.",
            "error": str(e),
        })


_meter = get_meter(__name__)
_active_sessions = _meter.create_up_down_counter(
    name="energize.coaching.sessions.active",
    description="Number of currently active WebSocket coaching sessions",
)


