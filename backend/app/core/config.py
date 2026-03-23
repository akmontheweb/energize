import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://energize:energize@localhost:5432/energize"
    KEYCLOAK_URL: str = "http://keycloak:8080"
    KEYCLOAK_REALM: str = "energize"
    KEYCLOAK_CLIENT_ID: str = "energize-backend"
    KEYCLOAK_CLIENT_SECRET: str = "CHANGE_ME_IN_PRODUCTION"
    KEYCLOAK_ADMIN: str = "admin"
    KEYCLOAK_ADMIN_PASSWORD: str = "admin"
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    SECRET_KEY: str = "change-me-in-production"
    LOG_LEVEL: str = "INFO"

    # ── LLM Provider (provider-agnostic) ──────────────────────────────────────
    # Supported: openai | anthropic | google_genai | azure_openai | mistralai
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2048
    LLM_STREAMING: bool = True

    # Deprecated — kept for backward compatibility. Migrate to LLM_API_KEY.
    OPENAI_API_KEY: str = ""

    # ── MCP Server ────────────────────────────────────────────────────────────
    MCP_SERVER_URL: str = "http://mcp-server:9000/sse"
    MCP_PORT: int = 9000

    # ── OpenTelemetry ──────────────────────────────────────────────────────────
    OTEL_SERVICE_NAME: str = "energize-backend"
    OTEL_ENABLED: bool = True
    # Set to a gRPC endpoint (e.g. http://otel-collector:4317) to enable OTLP export.
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_EXPORT_INTERVAL_MILLIS: int = 10000
    # WARNING: enabling this logs full prompt/completion content — may expose PII.
    OTEL_INCLUDE_PROMPT_CONTENT: bool = False

    @model_validator(mode="after")
    def _resolve_deprecated_openai_key(self) -> "Settings":
        """Fall back to OPENAI_API_KEY when LLM_API_KEY is unset and provider is openai."""
        if not self.LLM_API_KEY and self.OPENAI_API_KEY:
            logging.getLogger(__name__).warning(
                "OPENAI_API_KEY is deprecated. Set LLM_API_KEY=<your-key> in .env instead."
            )
            self.LLM_API_KEY = self.OPENAI_API_KEY
        return self

    class Config:
        env_file = ".env"


settings = Settings()
