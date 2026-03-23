-- =============================================================================
-- Energize Coaching Platform – PostgreSQL Schema
-- =============================================================================
-- Run with: psql -U energize -d energize -f schema.sql
-- NOTE: This file is kept in sync with Alembic migrations.
--       Migrations (alembic upgrade head) are the authoritative source for
--       the live database.  Use this file for documentation / fresh installs.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Enum Types
-- ---------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('client', 'coach', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE session_status AS ENUM ('active', 'completed', 'escalated', 'archived');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------------------------------------------------------------------------
-- Table: tenants
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants (slug);

COMMENT ON TABLE  tenants          IS 'One row per coaching organisation (Energize client company).';
COMMENT ON COLUMN tenants.slug     IS 'URL-safe unique identifier for the tenant.';

-- ---------------------------------------------------------------------------
-- Table: users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    keycloak_sub    VARCHAR(255) NOT NULL UNIQUE,
    email           VARCHAR(255) NOT NULL,
    role            user_role   NOT NULL DEFAULT 'client',
    tenant_id       UUID        NOT NULL REFERENCES tenants (id) ON DELETE RESTRICT,
    coach_id        UUID                 REFERENCES users (id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_keycloak_sub ON users (keycloak_sub);
CREATE INDEX IF NOT EXISTS idx_users_tenant_id    ON users (tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email        ON users (tenant_id, email);
CREATE INDEX IF NOT EXISTS idx_users_coach_id     ON users (coach_id);

COMMENT ON TABLE  users               IS 'Platform users provisioned on first Keycloak login.';
COMMENT ON COLUMN users.keycloak_sub  IS 'Keycloak subject claim (sub) – immutable identity key.';
COMMENT ON COLUMN users.role          IS 'Platform role: client | coach | admin.';
COMMENT ON COLUMN users.coach_id      IS 'Assigned coach for client users. NULL for coaches and admins.';

-- ---------------------------------------------------------------------------
-- Table: coaching_sessions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS coaching_sessions (
    id          UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    title       VARCHAR(255),
    client_id   UUID            NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    coach_id    UUID                     REFERENCES users (id) ON DELETE SET NULL,
    tenant_id   UUID            NOT NULL REFERENCES tenants (id) ON DELETE RESTRICT,
    status      session_status  NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_client_id  ON coaching_sessions (client_id);
CREATE INDEX IF NOT EXISTS idx_sessions_coach_id   ON coaching_sessions (coach_id);
CREATE INDEX IF NOT EXISTS idx_sessions_tenant_id  ON coaching_sessions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status     ON coaching_sessions (tenant_id, status);

COMMENT ON TABLE  coaching_sessions          IS 'One AI coaching conversation thread per row.';
COMMENT ON COLUMN coaching_sessions.title    IS 'User-defined session title shown in the UI.';
COMMENT ON COLUMN coaching_sessions.coach_id IS 'NULL until a human coach is assigned (escalation).';
COMMENT ON COLUMN coaching_sessions.status   IS 'active | completed | escalated | archived.';

-- Automatically keep updated_at current
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sessions_updated_at ON coaching_sessions;
CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON coaching_sessions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Table: messages
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id          UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  UUID            NOT NULL REFERENCES coaching_sessions (id) ON DELETE CASCADE,
    role        message_role    NOT NULL,
    content     TEXT            NOT NULL,
    metadata    JSONB                    DEFAULT '{}',
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_metadata   ON messages USING GIN (metadata);

COMMENT ON TABLE  messages          IS 'Individual chat turns within a coaching session.';
COMMENT ON COLUMN messages.role     IS 'user | assistant | system.';
COMMENT ON COLUMN messages.metadata IS 'Arbitrary JSON: token counts, node name, escalation flags, etc.';

-- ---------------------------------------------------------------------------
-- Table: coach_documents
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS coach_documents (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_id          VARCHAR(36) NOT NULL UNIQUE,
    coach_id        UUID        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    client_id       UUID        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    tenant_id       UUID        NOT NULL REFERENCES tenants (id) ON DELETE RESTRICT,
    filename        VARCHAR(512) NOT NULL,
    content_type    VARCHAR(128) NOT NULL DEFAULT 'application/octet-stream',
    file_bytes      BYTEA       NOT NULL,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_coach_documents_doc_id              ON coach_documents (doc_id);
CREATE INDEX IF NOT EXISTS idx_coach_documents_coach_id            ON coach_documents (coach_id);
CREATE INDEX IF NOT EXISTS idx_coach_documents_client_id           ON coach_documents (client_id);
CREATE INDEX IF NOT EXISTS idx_coach_documents_tenant_id           ON coach_documents (tenant_id);
CREATE INDEX IF NOT EXISTS idx_coach_documents_coach_client_active ON coach_documents (coach_id, client_id, tenant_id, is_active);

COMMENT ON TABLE  coach_documents              IS 'Original files uploaded by coaches for specific clients (past-interaction notes).';
COMMENT ON COLUMN coach_documents.doc_id       IS 'UUID string matching the ChromaDB coach-conversations metadata key.';
COMMENT ON COLUMN coach_documents.file_bytes   IS 'Raw uploaded file content for original-file download.';
COMMENT ON COLUMN coach_documents.is_active    IS 'FALSE = archived (superseded by a hard-replace upload).';

-- ---------------------------------------------------------------------------
-- Table: methodology_documents
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS methodology_documents (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_id          VARCHAR(36) NOT NULL UNIQUE,
    tenant_id       UUID        NOT NULL REFERENCES tenants (id) ON DELETE RESTRICT,
    filename        VARCHAR(512) NOT NULL,
    content_type    VARCHAR(128) NOT NULL DEFAULT 'application/octet-stream',
    file_bytes      BYTEA       NOT NULL,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    uploaded_by     UUID        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_methodology_documents_doc_id        ON methodology_documents (doc_id);
CREATE INDEX IF NOT EXISTS idx_methodology_documents_tenant_id     ON methodology_documents (tenant_id);
CREATE INDEX IF NOT EXISTS idx_methodology_documents_tenant_active ON methodology_documents (tenant_id, is_active);

COMMENT ON TABLE  methodology_documents              IS 'Original files uploaded by admins for methodology / coaching-procedure reference.';
COMMENT ON COLUMN methodology_documents.doc_id       IS 'UUID string matching the ChromaDB tenant resources metadata key.';
COMMENT ON COLUMN methodology_documents.file_bytes   IS 'Raw uploaded file content for original-file download.';
COMMENT ON COLUMN methodology_documents.is_active    IS 'FALSE = superseded row (replaced in-place via PUT).';

-- ---------------------------------------------------------------------------
-- Table: prompt_templates
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prompt_templates (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    key         VARCHAR(100) NOT NULL,
    tenant_id   UUID        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    value       TEXT        NOT NULL,
    is_json     BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by  UUID                 REFERENCES users (id) ON DELETE SET NULL,
    UNIQUE (key, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_prompt_templates_tenant_key ON prompt_templates (tenant_id, key);

COMMENT ON TABLE  prompt_templates        IS 'Admin-managed prompt templates per tenant. Seeded by Alembic migration 002.';
COMMENT ON COLUMN prompt_templates.key    IS 'Logical name: coach_system_prompt, guardrails_do, etc.';
COMMENT ON COLUMN prompt_templates.is_json IS 'TRUE when value is a JSON array (guardrails, keywords).';

-- ---------------------------------------------------------------------------
-- Seed: default "demo" tenant (remove in production)
-- ---------------------------------------------------------------------------
INSERT INTO tenants (id, name, slug)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'Energize Demo',
    'energize-demo'
)
ON CONFLICT (slug) DO NOTHING;

-- =============================================================================
-- End of schema
-- =============================================================================
