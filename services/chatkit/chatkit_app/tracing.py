from __future__ import annotations

import json
import threading
from typing import Any

from agents.tracing import set_trace_processors, set_tracing_disabled
from agents.tracing.processor_interface import TracingProcessor

from .config import _env, _is_truthy


def configure_tracing() -> None:
    mode = (_env("CHATKIT_TRACE_MODE", "openai") or "openai").lower()
    disable_env = _is_truthy(_env("OPENAI_AGENTS_DISABLE_TRACING"))

    if mode == "none":
        set_tracing_disabled(True)
        return

    if mode != "otel":
        set_tracing_disabled(disable_env)
        return

    if disable_env:
        set_tracing_disabled(True)
        return

    try:
        from opentelemetry import trace as otel_trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.trace import Status, StatusCode
    except Exception as exc:
        set_tracing_disabled(True)
        print(f"OTEL tracing disabled: {exc}")
        return

    raw_endpoint = _env("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317") or "localhost:4317"
    endpoint = raw_endpoint.strip()

    insecure_env = _env("OTEL_EXPORTER_OTLP_INSECURE")
    insecure = _is_truthy(insecure_env) if insecure_env is not None else None
    if insecure is None and endpoint.startswith(("localhost", "127.0.0.1", "0.0.0.0")):
        insecure = True

    service_name = _env("OTEL_SERVICE_NAME", "openai-agent-chatkit") or "openai-agent-chatkit"
    include_data = _is_truthy(_env("CHATKIT_TRACE_INCLUDE_DATA"))

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    otel_trace.set_tracer_provider(provider)
    tracer = otel_trace.get_tracer("chatkit")

    class OtelTracingProcessor(TracingProcessor):
        def __init__(self) -> None:
            self._traces: dict[str, Any] = {}
            self._spans: dict[str, Any] = {}
            self._lock = threading.Lock()

        def on_trace_start(self, trace) -> None:
            attributes = {
                "openai.trace_id": trace.trace_id,
            }
            if trace.group_id:
                attributes["openai.group_id"] = trace.group_id
            if trace.metadata and include_data:
                attributes["openai.metadata"] = json.dumps(
                    trace.metadata, ensure_ascii=True
                )

            span = tracer.start_span(trace.name, attributes=attributes)
            with self._lock:
                self._traces[trace.trace_id] = span

        def on_trace_end(self, trace) -> None:
            with self._lock:
                span = self._traces.pop(trace.trace_id, None)
            if span is not None:
                span.end()

        def on_span_start(self, span) -> None:
            parent_span = None
            with self._lock:
                if span.parent_id:
                    parent_span = self._spans.get(span.parent_id)
                if parent_span is None:
                    parent_span = self._traces.get(span.trace_id)

            context = (
                otel_trace.set_span_in_context(parent_span)
                if parent_span is not None
                else None
            )
            name = span.span_data.type
            data_name = getattr(span.span_data, "name", None)
            if data_name:
                name = f"{name}:{data_name}"
            attributes = {
                "openai.trace_id": span.trace_id,
                "openai.span_id": span.span_id,
                "openai.span_type": span.span_data.type,
            }
            if span.parent_id:
                attributes["openai.parent_id"] = span.parent_id

            otel_span = tracer.start_span(
                name,
                context=context,
                attributes=attributes,
            )
            with self._lock:
                self._spans[span.span_id] = otel_span

        def on_span_end(self, span) -> None:
            with self._lock:
                otel_span = self._spans.pop(span.span_id, None)
            if otel_span is None:
                return

            if include_data:
                otel_span.set_attribute(
                    "openai.span.data",
                    json.dumps(span.span_data.export(), ensure_ascii=True),
                )

            if span.error:
                otel_span.set_attribute(
                    "openai.span.error",
                    json.dumps(span.error, ensure_ascii=True),
                )
                message = span.error.get("message") if span.error else "span error"
                otel_span.set_status(Status(StatusCode.ERROR, message))

            otel_span.end()

        def shutdown(self) -> None:
            provider.shutdown()

        def force_flush(self) -> None:
            provider.force_flush()

    set_trace_processors([OtelTracingProcessor()])
    set_tracing_disabled(False)
