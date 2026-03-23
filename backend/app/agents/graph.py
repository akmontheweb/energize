import logging
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import CoachingState
# Agent nodes use MCP layer functions (mcp_server.resources.prompts and
# mcp_server.tools.chroma) for all prompt content and vector DB access.
from app.agents.nodes import (
    intake_node,
    coaching_node,
    reflection_node,
    retrieval_node,
    escalation_node,
)

logger = logging.getLogger(__name__)


# Description: Function `route_after_start` implementation.
# Inputs: state
# Output: str
# Exceptions: Propagates exceptions raised by internal operations.
def route_after_start(state: CoachingState) -> str:
    """Route to intake if no goals established, else coaching."""
    if not state.get("client_goals"):
        return "intake"
    return "retrieval"


# Description: Function `route_after_coaching` implementation.
# Inputs: state
# Output: str
# Exceptions: Propagates exceptions raised by internal operations.
def route_after_coaching(state: CoachingState) -> str:
    """Route after coaching node based on state."""
    if state.get("needs_escalation"):
        return "escalation"
    if state.get("phase") == "reflection":
        return "reflection"
    return END


# Description: Function `build_graph` implementation.
# Inputs: None
# Output: StateGraph
# Exceptions: Propagates exceptions raised by internal operations.
def build_graph() -> StateGraph:
    """Build and compile the LangGraph workflow used by the coaching chat."""
    builder = StateGraph(CoachingState)

    builder.add_node("intake", intake_node)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("coaching", coaching_node)
    builder.add_node("reflection", reflection_node)
    builder.add_node("escalation", escalation_node)

    builder.add_conditional_edges(
        START,
        route_after_start,
        {"intake": "intake", "retrieval": "retrieval"},
    )

    builder.add_edge("intake", "coaching")
    builder.add_edge("retrieval", "coaching")
    builder.add_conditional_edges(
        "coaching",
        route_after_coaching,
        {"escalation": "escalation", "reflection": "reflection", END: END},
    )
    builder.add_edge("reflection", END)
    builder.add_edge("escalation", END)

    memory = MemorySaver()
    logger.info("Compiled coaching graph with in-memory checkpointing")
    return builder.compile(checkpointer=memory)


coaching_graph = build_graph()
