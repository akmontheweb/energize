from typing import TypedDict, List, Annotated
from langchain_core.messages import BaseMessage
import operator


# Description: Class `CoachingState` encapsulates related data and behavior for this module.
class CoachingState(TypedDict):
    """State carried across the LangGraph coaching workflow."""

    messages: Annotated[List[BaseMessage], operator.add]
    session_id: str
    tenant_id: str
    client_id: str
    client_goals: List[str]
    phase: str  # "intake" | "coaching" | "reflection" | "escalated"
    retrieved_resources: List[str]
    needs_escalation: bool
