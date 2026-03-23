# Energize – LangGraph Agent Design

## 1. Overview

The Energize coaching agent is implemented as a LangGraph `StateGraph`. It orchestrates five specialised nodes that guide a coaching session from initial goal-setting through active coaching, resource retrieval, and optional escalation to a human coach.

---

## 2. Agent Graph

```
                        ┌─────────┐
                        │  START  │
                        └────┬────┘
                             │
                    has goals?│
               ┌─────────────┴─────────────┐
               │ NO                   YES  │
               ▼                           ▼
        ┌─────────────┐           ┌─────────────────┐
        │ intake_node │           │  retrieval_node  │
        │             │           │  (ChromaDB RAG)  │
        └──────┬──────┘           └────────┬─────────┘
               │                           │
               └─────────┬─────────────────┘
                          ▼
                  ┌───────────────┐
                  │ coaching_node │◀─────────────┐
                  │  (LLM core)   │              │
                  └──────┬────────┘              │
                         │                       │
            ┌────────────┼────────────┐          │
            │            │            │          │
     needs_escalation? ending?    continue?      │
            │            │            └──────────┘
            ▼            ▼
    ┌────────────┐ ┌──────────────┐
    │ escalation │ │ reflection   │
    │    _node   │ │    _node     │
    └─────┬──────┘ └──────┬───────┘
          │               │
          └───────┬────────┘
                  ▼
               ┌─────┐
               │ END │
               └─────┘
```

---

## 3. State Schema

```python
class CoachingState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]  # full conversation history
    session_id: str          # UUID of the CoachingSession record
    tenant_id: str           # tenant isolation key
    client_goals: List[str]  # extracted goals from intake
    phase: str               # "intake" | "coaching" | "reflection" | "escalated"
    retrieved_resources: List[str]  # relevant doc excerpts from ChromaDB
    needs_escalation: bool   # flag set by coaching_node keyword scan
```

---

## 4. Node Descriptions

### `intake_node`
**Triggered when**: `client_goals` is empty (first turn or no goals captured yet)

**Responsibility**: Extract the client's coaching goals from the conversation using an LLM call with a structured extraction prompt.

**System prompt**:
```
You are an empathetic intake coordinator for a professional coaching service.
Your job is to warmly welcome the client and understand their coaching goals.
Ask about their professional challenges, what they hope to achieve, and their
current situation. Extract 2-5 specific, actionable goals from the conversation.
Never mention you are an AI.
```

**Output**: Populates `state.client_goals`, sets `state.phase = "coaching"`

---

### `retrieval_node`
**Triggered when**: Entering the coaching phase (before `coaching_node`)

**Responsibility**: Query ChromaDB with the latest user message to retrieve relevant coaching resources, frameworks, or past session insights.

**Implementation**:
```python
collection = chroma_client.get_collection(f"{state['tenant_id']}_resources")
results = collection.query(
    query_texts=[last_user_message],
    n_results=3
)
state["retrieved_resources"] = results["documents"][0]
```

**Output**: Populates `state.retrieved_resources`

---

### `coaching_node`
**Triggered when**: Phase is `"coaching"` (main loop node)

**Responsibility**: Generate the AI coaching response using full conversation history, client goals, and retrieved resources. Also scans the response for escalation triggers.

**System prompt**:
```
You are a professional executive coach working for Energize coaching company.
You use evidence-based coaching techniques including GROW model, motivational
interviewing, and strengths-based approaches.

Client's goals: {client_goals}

Relevant coaching resources:
{retrieved_resources}

Guidelines:
- Ask powerful, open-ended questions
- Reflect back what you hear
- Challenge assumptions constructively
- Never give direct advice; guide through questions
- Keep responses concise (2-3 paragraphs max)
- Never reveal you are an AI
```

**Escalation detection** (keyword scan on user messages):
```python
ESCALATION_KEYWORDS = [
    "crisis", "suicidal", "harm myself", "can't cope",
    "emergency", "urgent help", "mental breakdown"
]
```

**Output**: Appends assistant message to `state.messages`, sets `needs_escalation` if triggered

---

### `reflection_node`
**Triggered when**: Session is ending (coach or client signals completion)

**Responsibility**: Generate a structured session summary for both client and coach records.

**System prompt**:
```
Summarise this coaching session. Include:
1. Goals discussed
2. Key insights that emerged
3. Action items the client committed to
4. Recommended focus areas for next session

Format as structured JSON.
```

**Output**: Saves summary to `Message(role="system", content=summary_json)` in DB, sets `phase = "completed"`

---

### `escalation_node`
**Triggered when**: `state.needs_escalation = True`

**Responsibility**: Safely acknowledge the client's situation, notify them that a human coach will follow up, and flag the session for immediate coach review.

**Fixed response** (not LLM-generated – deterministic for safety):
```
I hear that you're going through something very difficult right now.
Your wellbeing is the priority. I'm connecting you with one of our
human coaches who will reach out to you shortly. You're not alone.
```

**Side effects**:
- Sets `session.status = "escalated"` in PostgreSQL
- Sets `state.phase = "escalated"`

---

## 5. Routing Logic

```python
def route_after_coaching(state: CoachingState) -> str:
    if state["needs_escalation"]:
        return "escalation"
    if state["phase"] == "reflection":
        return "reflection"
    return "retrieval"   # continue coaching loop

def route_entry(state: CoachingState) -> str:
    if not state["client_goals"]:
        return "intake"
    return "retrieval"
```

---

## 6. Graph Assembly

```python
graph = StateGraph(CoachingState)

graph.add_node("intake", intake_node)
graph.add_node("retrieval", retrieval_node)
graph.add_node("coaching", coaching_node)
graph.add_node("reflection", reflection_node)
graph.add_node("escalation", escalation_node)

graph.add_conditional_edges(START, route_entry)
graph.add_edge("intake", "coaching")
graph.add_edge("retrieval", "coaching")
graph.add_conditional_edges("coaching", route_after_coaching)
graph.add_edge("reflection", END)
graph.add_edge("escalation", END)

checkpointer = MemorySaver()
compiled = graph.compile(checkpointer=checkpointer)
```

---

## 7. Checkpointing & State Persistence

LangGraph's `MemorySaver` holds in-process state per `thread_id` (mapped to `session_id`). On service restart, state is reconstructed by replaying messages from PostgreSQL. This ensures no session state is lost across pod restarts in Kubernetes.

---

## 8. LLM Configuration

```python
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7,       # balanced creativity for coaching responses
    streaming=True,        # enables token-by-token WebSocket delivery
    max_tokens=500,        # keep responses concise
)
```

Privacy: Only anonymised conversation text is passed to `llm.astream()`. No tenant IDs, user emails, or session UUIDs appear in LLM inputs.
