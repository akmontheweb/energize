# Energize Platform – Formal Architecture Document

## 1. Executive Summary

Energize is a multi-tenant AI-powered professional coaching platform. It connects clients with an AI coaching agent via a real-time chat interface, with human coaches able to review and take over sessions. The system enforces strict tenant isolation, role-based access control, and data privacy at the LLM boundary.

---

## 2. Component Inventory

### Layer 1 – Presentation (Frontend)
| Component | Technology | Responsibility |
|---|---|---|
| Auth Portal | Next.js + keycloak-js | SSO redirect, token storage |
| Chat Interface | React + WebSocket | Real-time message exchange |
| Session Sidebar | React + Zustand | Session list, navigation |
| Coach Dashboard | React | Review sessions, manage clients |
| API Client | Axios | Attaches Bearer JWT to all HTTP requests |
| WebSocket Manager | Native WS | Streaming token delivery, auto-reconnect |

### Layer 2 – Identity & Access Management
| Component | Technology | Responsibility |
|---|---|---|
| Keycloak Realm | Keycloak 24 | OIDC provider, user federation |
| Frontend Client | Public OIDC (PKCE) | Browser-safe auth, no client secret |
| Backend Client | Bearer-only | Token introspection |
| Roles | realm roles | `client`, `coach`, `admin` |
| JWKS Endpoint | Keycloak | Public keys for JWT signature verification |

### Layer 3 – Application & Orchestration (Backend)
| Component | Technology | Responsibility |
|---|---|---|
| API Server | FastAPI | HTTP routing, WebSocket upgrade |
| JWT Middleware | python-jose | Verify Keycloak tokens, extract claims |
| Dependency Injection | FastAPI deps | `current_user`, `tenant_id` per request |
| Agent Orchestrator | LangGraph | Stateful multi-node coaching graph |
| Session Manager | SQLAlchemy | Load/save session state to PostgreSQL |

### Layer 4 – Data & Persistence
| Component | Technology | Responsibility |
|---|---|---|
| Relational Store | PostgreSQL 16 | Users, tenants, sessions, messages |
| Vector Store | ChromaDB | Coaching resource embeddings (RAG) |
| Migrations | Alembic | Schema versioning |
| Multi-tenancy | App-layer filter | All queries scoped by `tenant_id` |

### Layer 5 – LLM Integration
| Component | Technology | Responsibility |
|---|---|---|
| LLM Client | LangChain-OpenAI | GPT-4o calls via OpenAI API |
| Privacy Guard | Custom preprocessor | Strip/anonymise PII before LLM call |
| Embedding Pipeline | OpenAI Embeddings | Convert documents → vectors for ChromaDB |

### Layer 6 – Infrastructure & Deployment
| Component | Technology | Responsibility |
|---|---|---|
| Local Dev | Docker Compose | All services on `energize-net` |
| Container Runtime | Docker | Image build for frontend + backend |
| Orchestration | Kubernetes | Production deployment |
| TLS Termination | Nginx Ingress + cert-manager | HTTPS for all external traffic |
| Autoscaling | HPA | Backend scales 2→10 pods on CPU |

---

## 3. Security Boundaries

```
╔══════════════════════════════════════════════════════════════╗
║                    PUBLIC INTERNET                           ║
╠══════════════════════════════════════════════════════════════╣
║  TLS Boundary: Nginx Ingress (HTTPS/WSS only)                ║
╠══════════════════════════════════════════════════════════════╣
║  Auth Boundary: Keycloak OIDC (all requests need JWT)        ║
║  ┌─────────────┐      ┌───────────────────────────────────┐  ║
║  │  Frontend   │      │  Backend (JWT verified on entry)  │  ║
║  │  (browser)  │─────▶│  - tenant_id extracted from JWT   │  ║
║  └─────────────┘      │  - role checked per endpoint      │  ║
║                       └──────────────┬────────────────────┘  ║
╠══════════════════════════════════════╪═══════════════════════╣
║  Data Boundary: Internal network only║                        ║
║                       ┌─────────────▼─────────────────────┐  ║
║                       │  PostgreSQL  │  ChromaDB           │  ║
║                       │  (per-tenant │  (per-tenant        │  ║
║                       │   filtering) │   collections)      │  ║
║                       └─────────────────────────────────────┘  ║
╠══════════════════════════════════════════════════════════════╣
║  External API Boundary: OpenAI (anonymised data only)        ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 4. Authentication Flow

```
User Browser          Frontend            Keycloak            Backend
     │                    │                   │                   │
     │  Open app          │                   │                   │
     │──────────────────▶│                   │                   │
     │                    │  Not authenticated│                   │
     │                    │  redirect to KC   │                   │
     │                    │──────────────────▶│                   │
     │  Login page        │                   │                   │
     │◀───────────────────────────────────────│                   │
     │  Enter credentials │                   │                   │
     │──────────────────────────────────────▶│                   │
     │                    │  Auth code (PKCE) │                   │
     │                    │◀──────────────────│                   │
     │                    │  Exchange for JWT │                   │
     │                    │──────────────────▶│                   │
     │                    │  access_token     │                   │
     │                    │  refresh_token    │                   │
     │                    │◀──────────────────│                   │
     │                    │  Store in Zustand │                   │
     │  App loads         │                   │                   │
     │◀───────────────────│                   │                   │
     │                    │                   │                   │
     │  API call          │  Bearer <token>   │                   │
     │──────────────────▶│──────────────────────────────────────▶│
     │                    │                   │  Verify JWKS      │
     │                    │                   │◀──────────────────│
     │                    │                   │  Public key       │
     │                    │                   │──────────────────▶│
     │                    │                   │  JWT valid        │
     │  Response          │◀──────────────────────────────────────│
     │◀───────────────────│                   │                   │
```

---

## 5. Chat Session Flow

```
Client Browser    Frontend WS Mgr    Backend WS     LangGraph Agent    ChromaDB    OpenAI
      │                 │                │                │                │           │
      │  Send message   │                │                │                │           │
      │────────────────▶│                │                │                │           │
      │                 │  WS send text  │                │                │           │
      │                 │───────────────▶│                │                │           │
      │                 │                │  Save to DB    │                │           │
      │                 │                │  (role=user)   │                │           │
      │                 │                │                │                │           │
      │                 │                │  graph.ainvoke │                │           │
      │                 │                │───────────────▶│                │           │
      │                 │                │                │  retrieval_node│           │
      │                 │                │                │───────────────▶│           │
      │                 │                │                │  similar docs  │           │
      │                 │                │                │◀───────────────│           │
      │                 │                │                │                │           │
      │                 │                │                │  coaching_node │           │
      │                 │                │                │───────────────────────────▶│
      │                 │                │                │  stream tokens │           │
      │                 │                │                │◀───────────────────────────│
      │                 │                │  stream token  │                │           │
      │                 │◀───────────────│◀───────────────│                │           │
      │  Token arrives  │                │                │                │           │
      │◀────────────────│                │                │                │           │
      │  (repeat per    │                │                │                │           │
      │   token)        │                │                │                │           │
      │                 │                │  Save to DB    │                │           │
      │                 │                │  (role=asst.)  │                │           │
      │                 │                │  Send {"type": "done"}         │           │
      │                 │◀───────────────│                │                │           │
      │  Chat complete  │                │                │                │           │
      │◀────────────────│                │                │                │           │
```

---

## 6. Multi-Tenancy Isolation Strategy

| Layer | Isolation Method |
|---|---|
| JWT | `tenant_id` claim extracted from Keycloak token |
| API | `get_tenant_id()` FastAPI dependency; injected into every handler |
| PostgreSQL | All queries include `WHERE tenant_id = :tenant_id` filter |
| ChromaDB | Collections named `{tenant_id}_resources`; no cross-tenant queries |
| Agent State | `CoachingState.tenant_id` passed through entire graph |
| File uploads | (future) S3 prefix keyed by tenant |

---

## 7. Data Privacy at LLM Boundary

**What IS sent to OpenAI:**
- Anonymised coaching conversation text
- Session phase and goals (no names/identifiers)
- Retrieved coaching resource excerpts

**What is NOT sent to OpenAI:**
- User real names or email addresses
- Tenant identifiers
- Session UUIDs
- Any data from other tenants

The `coaching_node` receives `state.messages` which contain only conversation text. User identity is never embedded in the system prompt or message content passed to the LLM.

---

## 8. Data Flow Diagram

```
[Browser] ──HTTPS──▶ [Ingress] ──HTTP──▶ [Frontend :3000]
                          │
                          └──HTTP──▶ [Keycloak :8080]
                          │
                          └──HTTP──▶ [Backend :8000]
                                          │
                          ┌───────────────┼───────────────┐
                          │               │               │
                    [PostgreSQL]    [ChromaDB]      [OpenAI API]
                     :5432           :8000           (external)
```
