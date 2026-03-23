"""
OpenTelemetry setup for the Energize backend.

Signals instrumented
--------------------
* Traces  — one span per HTTP request (FastAPI) + one span per agent node + one
            span per LLM call using the OTel GenAI semantic conventions.
* Metrics — token-usage histograms, operation-duration histograms, and an
            active-sessions up/down counter (recorded in chat.py).
* Logs    — trace_id / span_id injected into every log record via
            LoggingInstrumentor so that logs can be correlated with traces.

Exporters
---------
Console (stdout) exporters are always active — useful for development and
container log aggregation.  OTLP gRPC exporters are added automatically when
OTEL_EXPORTER_OTLP_ENDPOINT is set in the environment.

Usage
-----
Call ``setup_telemetry(app)`` once after the FastAPI application object has
been created (before the first request is processed).
Obtain a tracer or meter anywhere in the codebase via the helpers:

    from app.core.telemetry import get_tracer, get_meter

    tracer = get_tracer(__name__)
    meter  = get_meter(__name__)
"""

import logging

from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


def setup_telemetry(app=None) -> None:
    """
    Initialise OpenTelemetry tracing, metrics, and logging instrumentation.

    Parameters
    ----------
    app:
        The FastAPI application instance.  When provided, FastAPIInstrumentor
        will automatically create spans for every incoming HTTP request.
    """
    if not settings.OTEL_ENABLED:
        logger.info("OpenTelemetry disabled (OTEL_ENABLED=false)")
        return

    resource = Resource.create({SERVICE_NAME: settings.OTEL_SERVICE_NAME})

    # ── Tracer Provider ───────────────────────────────────────────────────────
    tracer_provider = TracerProvider(resource=resource)

    # Console exporter — always active; writes JSON spans to stdout.
    tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )

        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
            )
        )

    trace.set_tracer_provider(tracer_provider)

    # ── Meter Provider ────────────────────────────────────────────────────────
    readers = [
        PeriodicExportingMetricReader(
            ConsoleMetricExporter(),
            export_interval_millis=settings.OTEL_EXPORT_INTERVAL_MILLIS,
        )
    ]

    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (  # noqa: PLC0415
            OTLPMetricExporter,
        )

        readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT),
                export_interval_millis=settings.OTEL_EXPORT_INTERVAL_MILLIS,
            )
        )

    meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(meter_provider)

    # ── Logging — inject trace_id / span_id into every log record ────────────
    # set_logging_format=False so we don't override the format set in
    # logging_utils.configure_logging; our OtelTraceContextFilter provides
    # safe defaults for records emitted outside of an active span.
    LoggingInstrumentor().instrument(set_logging_format=False)

    # ── HTTP client instrumentation (covers outbound Keycloak/httpx calls) ───
    HTTPXClientInstrumentor().instrument()

    # ── SQLAlchemy auto-instrumentation ──────────────────────────────────────
    SQLAlchemyInstrumentor().instrument()

    # ── FastAPI auto-instrumentation ─────────────────────────────────────────
    if app is not None:
        FastAPIInstrumentor.instrument_app(app)

    logger.info(
        "OpenTelemetry initialised service=%s otlp_enabled=%s include_prompt_content=%s",
        settings.OTEL_SERVICE_NAME,
        bool(settings.OTEL_EXPORTER_OTLP_ENDPOINT),
        settings.OTEL_INCLUDE_PROMPT_CONTENT,
    )


def get_tracer(name: str = "energize") -> trace.Tracer:
    """Return the OTel tracer for the given instrumentation scope."""
    return trace.get_tracer(name)


def get_meter(name: str = "energize") -> metrics.Meter:
    """Return the OTel meter for the given instrumentation scope."""
    return metrics.get_meter(name)
