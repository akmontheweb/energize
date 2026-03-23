# Energize – AI-Powered Professional Coaching Platform

An end-to-end application for the Energize coaching company, featuring a real-time AI chat interface backed by a multi-agent LangGraph orchestration engine, Keycloak-based identity management, and full multi-tenant data isolation.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERNET / CLIENT                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS / WSS
                    ┌──────▼──────┐
                    │   INGRESS   │  (Nginx + TLS / cert-manager)
                    └──┬──────┬───┘
                       │      │
            ┌──────────▼─┐  ┌─▼────────────┐
            │  FRONTEND  │  │   KEYCLOAK   │
            │  Next.js   │  │   IAM/SSO    │
            │  (Port 3000)│  │  (Port 8080) │
            └──────────┬─┘  └─────────────┘
                       │ REST + WebSocket (JWT)
                  ┌────▼────────────┐
                  │    BACKEND      │
                  │  FastAPI        │
                  │  LangGraph      │
                  │  (Port 8000)    │
                  └──┬──────────┬──┘
                     │          │
          ┌──────────▼─┐    ┌───▼──────────┐    ┌─────────────┐
          │ PostgreSQL  │    │  pgvector    │    │  OpenAI API │
          │ (sessions,  │    │  (vector     │    │  (LLM       │
          │  messages)  │    │   search)    │    │   engine)   │
          └─────────────┘    └──────────────┘    └─────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS |
| Identity & Access | Keycloak 24 (OIDC/OAuth2, PKCE) |
| Backend API | Python 3.11, FastAPI, WebSockets |
| Agent Orchestration | LangGraph, LangChain |
| LLM | OpenAI GPT-4o |
| Relational DB | PostgreSQL 16 + pgvector |
| Vector Search | pgvector (embedded in PostgreSQL) |
| Containerisation | Docker, Docker Compose |
| Orchestration | Kubernetes (k8s manifests included) |

---

## Quick Start (Docker Compose)

```bash
# 1. Clone and enter project
cd c:\akhil\projects\energize

# 2. Copy and fill environment file
cp infrastructure/.env.example infrastructure/.env

# 3. Start all services
cd infrastructure
docker compose up --build

# 4. Access the app
# Frontend:  http://localhost:3000
# API docs:  http://localhost:8000/docs
# Keycloak:  http://localhost:8080
```

> **First run**: Keycloak will auto-import the `energize` realm from `infrastructure/keycloak/realm-export.json`.  
> Create a test user at http://localhost:8080/admin (admin/admin) → Realm: energize → Users → Add user.

---

## Development Setup

### Backend

```bash
cd backend

# Create virtualenv
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Copy env
cp .env.example .env          # edit DATABASE_URL, OPENAI_API_KEY etc.

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy env
cp .env.local.example .env.local   # edit Keycloak + API URLs

# Start dev server
npm run dev                         # http://localhost:3000
```

---

## Environment Variables

| Variable | Service | Description |
|---|---|---|
| `DATABASE_URL` | backend | PostgreSQL async DSN |
| `KEYCLOAK_URL` | backend | Keycloak base URL |
| `KEYCLOAK_REALM` | backend | Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | backend | Backend client ID |
| `OPENAI_API_KEY` | backend | OpenAI API key |
| `EMBEDDING_MODEL` | backend | Embedding model (auto-resolved from `LLM_PROVIDER`) |
| `EMBEDDING_DIMENSIONS` | backend | Vector dimensions (1536 openai, 768 google, 1024 mistral) |
| `NEXT_PUBLIC_KEYCLOAK_URL` | frontend | Keycloak URL (browser) |
| `NEXT_PUBLIC_KEYCLOAK_REALM` | frontend | Keycloak realm |
| `NEXT_PUBLIC_KEYCLOAK_CLIENT_ID` | frontend | Frontend client ID |
| `NEXT_PUBLIC_API_URL` | frontend | Backend API base URL |

Full reference: `infrastructure/.env.example`

---

## Keycloak Setup

The realm is auto-imported in Docker Compose. For manual import:

1. Start Keycloak: `docker run -p 8080:8080 -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin quay.io/keycloak/keycloak:24.0.4 start-dev`
2. Open http://localhost:8080/admin
3. Create realm → Import `infrastructure/keycloak/realm-export.json`

**Roles**: `client` (default), `coach`, `admin`  
**Clients**: `energize-frontend` (public, PKCE), `energize-backend` (bearer-only)

---

## Database Migrations

```bash
cd backend

# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/auth/me` | Required | Current user info |
| GET | `/api/v1/sessions` | Required | List sessions |
| POST | `/api/v1/sessions` | Required | Create session |
| GET | `/api/v1/sessions/{id}` | Required | Session + messages |
| PATCH | `/api/v1/sessions/{id}` | Required | Update session status |
| POST | `/api/v1/embeddings/ingest` | coach/admin | Ingest documents |
| WS | `/api/v1/ws/chat/{session_id}` | token query param | Real-time chat |

Interactive docs: http://localhost:8000/docs

---

## WebSocket Chat Protocol

**Connect**: `ws://localhost:8000/api/v1/ws/chat/{session_id}?token={jwt_access_token}`

**Send** (text):
```
Hello, I need help with work-life balance.
```

**Receive** (streaming JSON, one token per message):
```json
{"type": "token", "content": "I"}
{"type": "token", "content": " understand"}
{"type": "done", "session_id": "uuid"}
```

---

## Deployment (Kubernetes)

```bash
cd infrastructure/kubernetes

# Apply all manifests
kubectl apply -f namespace.yaml
kubectl apply -f secrets.yaml     # Update with real base64 secrets first!
kubectl apply -f postgres/
kubectl apply -f keycloak/
kubectl apply -f backend/
kubectl apply -f frontend/
kubectl apply -f ingress.yaml

# Monitor
kubectl get pods -n energize
kubectl logs -n energize deploy/backend -f
```

Update `infrastructure/kubernetes/secrets.yaml` with real base64-encoded values before deploying.

---

## Security

- All API endpoints require a valid Keycloak JWT (`Authorization: Bearer <token>`)
- WebSocket connections authenticated via `?token=` query parameter
- Multi-tenant isolation: every DB query scoped by `tenant_id` from the JWT
- ChromaDB collections namespaced per tenant
- **No PII sent to OpenAI**: messages are anonymised at the LLM integration boundary
- Row-level isolation enforced in all query filters (not DB RLS, but application-layer)
- PKCE required for the frontend client (no client secret in browser)
- Access tokens expire in 15 minutes; refresh tokens in 8 hours

---

## Project Structure

```
energize/
├── frontend/          # Next.js 14 app
├── backend/           # FastAPI + LangGraph app
├── infrastructure/    # Docker Compose + Kubernetes + Keycloak
├── docs/              # Architecture & design docs
└── README.md
```

---

## Contributing

1. Create a feature branch from `main`
2. Follow existing code patterns (async/await throughout)
3. Add tests for new business logic
4. Open a PR with description of changes
