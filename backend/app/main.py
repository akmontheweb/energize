import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.logging_utils import configure_logging
from app.core.telemetry import setup_telemetry
from app.db.database import engine, Base
from app.api.routes import auth, sessions, chat, embeddings, users, prompts

configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Description: Function `lifespan` implementation.
# Inputs: app
# Output: Varies by implementation
# Exceptions: Propagates exceptions raised by internal operations.
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Energize API", extra={"log_level": settings.LOG_LEVEL})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Backfill schema changes for existing deployments without requiring manual migration.
        await conn.execute(text("ALTER TABLE coaching_sessions ADD COLUMN IF NOT EXISTS title VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS coach_id UUID REFERENCES users(id)"))
    yield
    logger.info("Shutting down Energize API")


app = FastAPI(
    title="Energize Coaching API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise OpenTelemetry.  Must be called after the app object is created so
# that FastAPIInstrumentor can wrap it.  Console exporters are always active;
# OTLP is added automatically when OTEL_EXPORTER_OTLP_ENDPOINT is set.
setup_telemetry(app)


# Description: Function `add_request_context` implementation.
# Inputs: request, call_next
# Output: Varies by implementation
# Exceptions: Propagates exceptions raised by internal operations.
@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    started_at = time.perf_counter()

    logger.info(
        "Request started request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )

    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-ID"] = request_id

    logger.info(
        "Request completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# Description: Function `validation_exception_handler` implementation.
# Inputs: request, exc
# Output: Varies by implementation
# Exceptions: Propagates exceptions raised by internal operations.
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(
        "Validation error request_id=%s method=%s path=%s errors=%s",
        request_id,
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed. Review request payload and schema.",
            "errors": exc.errors(),
            "request_id": request_id,
        },
    )


# Description: Function `unhandled_exception_handler` implementation.
# Inputs: request, exc
# Output: Varies by implementation
# Exceptions: Propagates exceptions raised by internal operations.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        "Unhandled error request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error. Contact operations with the provided request_id.",
            "request_id": request_id,
        },
    )

app.include_router(auth.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(embeddings.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(prompts.router, prefix="/api/v1")


# Description: Function `health_check` implementation.
# Inputs: None
# Output: Varies by implementation
# Exceptions: Propagates exceptions raised by internal operations.
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "energize-api"}
