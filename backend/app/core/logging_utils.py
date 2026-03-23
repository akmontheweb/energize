import logging
import logging.config


class OtelTraceContextFilter(logging.Filter):
    """
    Provide safe defaults for the ``otelTraceID`` and ``otelSpanID`` log-record
    attributes injected by OpenTelemetry's LoggingInstrumentor.

    Without this filter, log records emitted *before* an active OTel span (e.g.
    at startup) would cause a KeyError when the formatter tries to expand
    ``%(otelTraceID)s`` / ``%(otelSpanID)s``.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if not hasattr(record, "otelTraceID"):
            record.otelTraceID = "0"  # type: ignore[attr-defined]
        if not hasattr(record, "otelSpanID"):
            record.otelSpanID = "0"  # type: ignore[attr-defined]
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure application-wide structured logging once at startup."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    # trace_id / span_id are populated by OtelTraceContextFilter
                    # (defaults to 0) and enriched by LoggingInstrumentor once
                    # OpenTelemetry is initialised, enabling log-trace correlation.
                    "format": (
                        "%(asctime)s %(levelname)s [%(name)s] "
                        "trace_id=%(otelTraceID)s span_id=%(otelSpanID)s "
                        "%(message)s"
                    ),
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                }
            },
            "root": {
                "level": level.upper(),
                "handlers": ["default"],
            },
        }
    )
    # Attach the filter programmatically — avoids dictConfig's fully-qualified
    # class-path lookup which would fail on a private/underscore-named class.
    _otel_filter = OtelTraceContextFilter()
    for handler in logging.root.handlers:
        handler.addFilter(_otel_filter)