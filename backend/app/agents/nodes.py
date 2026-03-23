import logging
import time
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, SystemMessage
from opentelemetry import trace as otel_trace

from app.agents.state import CoachingState
from app.core.config import settings
from app.core.llm import get_llm
from app.core.telemetry import get_meter, get_tracer
from mcp_server.resources.prompts import (
    get_coach_system_prompt,
    get_escalation_keywords,
    get_escalation_message,
    get_intake_extraction_prompt,
    get_reflection_summary_prompt,
)
from mcp_server.tools.chroma import chroma_query_coach_docs, chroma_query_methodology_docs

logger = logging.getLogger(__name__)

# Lazy LLM initialisation — the provider is resolved once on first call.
_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


# ── OTel instrumentation ──────────────────────────────────────────────────────
_tracer = get_tracer(__name__)
_meter = get_meter(__name__)

_token_usage_hist = _meter.create_histogram(
    name="gen_ai.client.token.usage",
    description="Number of tokens used by LLM operations",
    unit="token",
)
_op_duration_hist = _meter.create_histogram(
    name="gen_ai.client.operation.duration",
    description="Duration of individual LLM operations",
    unit="s",
)
_node_duration_hist = _meter.create_histogram(
    name="energize.agent.node.duration",
    description="Duration of individual agent node execution",
    unit="s",
)


async def _invoke_llm(messages: list, operation_name: str):
    """
    Invoke the LLM inside an OpenTelemetry span that follows the GenAI
    semantic conventions (https://opentelemetry.io/docs/specs/semconv/gen-ai/).

    Span attributes set unconditionally
    ------------------------------------
    gen_ai.system, gen_ai.request.model, gen_ai.request.temperature,
    gen_ai.request.max_tokens, gen_ai.operation.name,
    gen_ai.usage.prompt_tokens, gen_ai.usage.completion_tokens,
    gen_ai.response.finish_reasons  (when available)

    Span attributes gated on OTEL_INCLUDE_PROMPT_CONTENT
    -----------------------------------------------------
    gen_ai.prompt, gen_ai.completion
    """
    llm = _get_llm()
    op_attrs: Dict[str, Any] = {
        "gen_ai.system": settings.LLM_PROVIDER,
        "gen_ai.request.model": settings.LLM_MODEL,
        "gen_ai.operation.name": operation_name,
    }

    with _tracer.start_as_current_span(f"gen_ai.{operation_name}") as span:
        span.set_attribute("gen_ai.system", settings.LLM_PROVIDER)
        span.set_attribute("gen_ai.request.model", settings.LLM_MODEL)
        span.set_attribute("gen_ai.request.temperature", settings.LLM_TEMPERATURE)
        span.set_attribute("gen_ai.request.max_tokens", settings.LLM_MAX_TOKENS)
        span.set_attribute("gen_ai.operation.name", operation_name)

        if settings.OTEL_INCLUDE_PROMPT_CONTENT:
            prompt_text = "\n".join(str(getattr(m, "content", "")) for m in messages)
            span.set_attribute("gen_ai.prompt", prompt_text[:8_000])

        t0 = time.perf_counter()
        try:
            response = await llm.ainvoke(messages)
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(otel_trace.StatusCode.ERROR, str(exc))
            raise
        finally:
            _op_duration_hist.record(time.perf_counter() - t0, op_attrs)

        # ── Token usage ───────────────────────────────────────────────────────
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            token_usage = getattr(response, "response_metadata", {}).get("token_usage", {})
            prompt_tokens = int(
                token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or 0
            )
            completion_tokens = int(
                token_usage.get("completion_tokens") or token_usage.get("output_tokens") or 0
            )
        else:
            prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "output_tokens", 0) or 0)

        if prompt_tokens:
            span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
            _token_usage_hist.record(prompt_tokens, {**op_attrs, "gen_ai.token.type": "input"})
        if completion_tokens:
            span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
            _token_usage_hist.record(
                completion_tokens, {**op_attrs, "gen_ai.token.type": "output"}
            )

        # ── Finish reason ─────────────────────────────────────────────────────
        finish_reason = (
            getattr(response, "response_metadata", {}).get("finish_reason")
            if hasattr(response, "response_metadata")
            else None
        )
        if finish_reason:
            span.set_attribute("gen_ai.response.finish_reasons", [finish_reason])

        if settings.OTEL_INCLUDE_PROMPT_CONTENT:
            span.set_attribute("gen_ai.completion", str(response.content)[:8_000])

        span.set_status(otel_trace.StatusCode.OK)
        return response


async def intake_node(state: CoachingState) -> Dict[str, Any]:
    """Extract client goals from initial messages using LLM."""
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("energize.agent.node") as span:
        span.set_attribute("node.name", "intake")
        try:
            messages = state["messages"]
            if not messages:
                return {"phase": "intake", "client_goals": []}

            conversation = "\n".join(
                f"{m.type}: {m.content}" for m in messages[-5:] if hasattr(m, "content")
            )

            extraction_prompt = (
                (await get_intake_extraction_prompt())
                .format(conversation=conversation)
            )

            response = await _invoke_llm(
                [SystemMessage(content=extraction_prompt)],
                "intake_extraction",
            )
            goals_text = response.content.strip()

            if goals_text == "NONE" or not goals_text:
                logger.info(
                    "Intake node found no explicit goals session_id=%s",
                    state.get("session_id"),
                )
                return {"phase": "intake", "client_goals": []}

            goals = [g.strip("- •").strip() for g in goals_text.split("\n") if g.strip()]
            logger.info(
                "Intake node extracted goals session_id=%s goal_count=%s",
                state.get("session_id"),
                len(goals),
            )
            return {"phase": "coaching", "client_goals": goals}
        finally:
            _node_duration_hist.record(time.perf_counter() - t0, {"node.name": "intake"})


async def retrieval_node(state: CoachingState) -> Dict[str, Any]:
    """Query ChromaDB for relevant coaching resources."""
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("energize.agent.node") as span:
        span.set_attribute("node.name", "retrieval")
        try:
            messages = state["messages"]
            tenant_id = state.get("tenant_id", "default")

            if not messages:
                return {"retrieved_resources": []}

            last_user_message = ""
            for m in reversed(messages):
                if hasattr(m, "type") and m.type == "human":
                    last_user_message = m.content
                    break

            if not last_user_message:
                return {"retrieved_resources": []}

            goals = state.get("client_goals", [])
            query = last_user_message
            if goals:
                query = f"{last_user_message} Goals: {', '.join(goals[:3])}"

            client_id = state.get("client_id", "")

            # Coach-client conversation docs queried first (higher contextual priority)
            coach_docs: List[str] = []
            if client_id:
                coach_docs = chroma_query_coach_docs(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    query=query,
                    n_results=3,
                )

            # Methodology docs uploaded by admin
            method_docs = chroma_query_methodology_docs(
                tenant_id=tenant_id, query=query, n_results=2
            )

            resources = coach_docs + method_docs
            span.set_attribute("retrieval.coach_docs", len(coach_docs))
            span.set_attribute("retrieval.method_docs", len(method_docs))
            logger.info(
                "Retrieval node completed session_id=%s coach_docs=%s method_docs=%s total=%s",
                state.get("session_id"),
                len(coach_docs),
                len(method_docs),
                len(resources),
            )
            return {"retrieved_resources": resources}
        finally:
            _node_duration_hist.record(time.perf_counter() - t0, {"node.name": "retrieval"})


async def coaching_node(state: CoachingState) -> Dict[str, Any]:
    """Main coaching LLM response node."""
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("energize.agent.node") as span:
        span.set_attribute("node.name", "coaching")
        try:
            messages = state["messages"]
            goals = state.get("client_goals", [])
            resources = state.get("retrieved_resources", [])

            system_content = await get_coach_system_prompt()
            if goals:
                system_content += "\n\nClient's current goals:\n" + "\n".join(
                    f"- {g}" for g in goals
                )
            if resources:
                system_content += "\n\nRelevant resources to draw from:\n" + "\n".join(
                    f"- {r}" for r in resources
                )

            full_messages = [SystemMessage(content=system_content)] + list(messages)
            response = await _invoke_llm(full_messages, "coaching_response")

            # Check for escalation triggers
            escalation_keywords: list[str] = await get_escalation_keywords()
            needs_escalation = any(
                kw in response.content.lower()
                or (messages and kw in messages[-1].content.lower())
                for kw in escalation_keywords
            )

            span.set_attribute("coaching.needs_escalation", needs_escalation)
            span.set_attribute("coaching.goal_count", len(goals))
            span.set_attribute("coaching.resource_count", len(resources))
            logger.info(
                "Coaching node completed session_id=%s escalation=%s goal_count=%s resource_count=%s",
                state.get("session_id"),
                needs_escalation,
                len(goals),
                len(resources),
            )
            return {
                "messages": [AIMessage(content=response.content)],
                "needs_escalation": needs_escalation,
            }
        finally:
            _node_duration_hist.record(time.perf_counter() - t0, {"node.name": "coaching"})


async def reflection_node(state: CoachingState) -> Dict[str, Any]:
    """Generate a session summary when the session ends."""
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("energize.agent.node") as span:
        span.set_attribute("node.name", "reflection")
        try:
            messages = state["messages"]
            goals = state.get("client_goals", [])

            conversation = "\n".join(
                f"{m.type}: {m.content}" for m in messages if hasattr(m, "content")
            )

            summary_prompt = (
                (await get_reflection_summary_prompt())
                .format(
                    goals=", ".join(goals) if goals else "Not yet established",
                    transcript=conversation[-3000:],
                )
                .strip()
            )

            response = await _invoke_llm(
                [SystemMessage(content=summary_prompt)],
                "reflection_summary",
            )
            summary_message = AIMessage(
                content=f"**Session Summary**\n\n{response.content}"
            )

            logger.info(
                "Reflection node generated summary session_id=%s",
                state.get("session_id"),
            )
            return {
                "messages": [summary_message],
                "phase": "reflection",
            }
        finally:
            _node_duration_hist.record(time.perf_counter() - t0, {"node.name": "reflection"})


async def escalation_node(state: CoachingState) -> Dict[str, Any]:
    """Handle escalation - notify that a human coach should intervene."""
    t0 = time.perf_counter()
    with _tracer.start_as_current_span("energize.agent.node") as span:
        span.set_attribute("node.name", "escalation")
        try:
            escalation_message = AIMessage(
                content=await get_escalation_message()
            )
            logger.warning(
                "Escalation node triggered session_id=%s", state.get("session_id")
            )
            return {
                "messages": [escalation_message],
                "phase": "escalated",
                "needs_escalation": False,
            }
        finally:
            _node_duration_hist.record(time.perf_counter() - t0, {"node.name": "escalation"})
