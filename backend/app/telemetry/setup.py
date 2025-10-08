import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

import orjson
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Extract trace context if available
        span = trace.get_current_span()
        span_context = span.get_span_context() if span is not None else None
        trace_id = None
        if span_context and span_context.is_valid:
            trace_id = format(span_context.trace_id, "032x")

        base: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if trace_id:
            base["trace.id"] = trace_id

        # Include extra attributes if present
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            base.update(record.extra_fields)

        return orjson.dumps(base).decode("utf-8")


def setup_telemetry_and_logging(service_name: str = "aegis-gateway") -> None:
    # Tracing
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(provider)

    # FastAPI auto-instrumentation will be applied in main via FastAPIInstrumentor.instrument_app()
    # Logging (structured JSON to stdout and to file)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    json_formatter = JsonLogFormatter()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(json_formatter)

    logs_dir = os.getenv("LOGS_DIR", "./logs")
    file_handler = RotatingFileHandler(
        filename=os.path.join(logs_dir, "aegis.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=2,
    )
    file_handler.setFormatter(json_formatter)

    # Avoid duplicate handlers in reloads
    logger.handlers = [stream_handler, file_handler]

    # FastAPI instrumentation will be done in main.py


