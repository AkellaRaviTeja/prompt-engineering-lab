"""OpenTelemetry traces with the GenAI semantic convention attributes.

Every `lantern.chat` call is a span named `chat <model>` carrying `gen_ai.*` attributes (provider,
model, temperature, max tokens, input, output and cached tokens, finish reason). A multi-step
run (the capstone pipeline, an eval) wraps its steps in `trace.span("step name")`, so each chat
span nests under the step that made it.

Spans are written, one JSON object per line, to `.progress/traces.jsonl` (git ignores it). Set
LANTERN_TRACE=0 to turn them off, or OTEL_EXPORTER_OTLP_ENDPOINT to also send them to a
collector (Jaeger, Phoenix, Langfuse) when `opentelemetry-exporter-otlp` is installed.
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any

from opentelemetry import trace as ot
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

from lantern.config import ROOT

if TYPE_CHECKING:
    from lantern.llm import Reply

PATH = ROOT / ".progress" / "traces.jsonl"
_tracer: ot.Tracer | None = None


class JsonlExporter(SpanExporter):
    def __init__(self, path=None):
        self.path = path  # None: the module's PATH, read at export time

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        path = self.path or PATH
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                for s in spans:
                    f.write(json.dumps(json.loads(s.to_json()), separators=(",", ":")) + "\n")
        except OSError:
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS


def tracer() -> ot.Tracer:
    global _tracer
    if _tracer is None:
        provider = TracerProvider(resource=Resource.create({"service.name": "lantern"}))
        if os.getenv("LANTERN_TRACE", "1") != "0":
            provider.add_span_processor(SimpleSpanProcessor(JsonlExporter()))
        if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
            except ImportError:
                pass
        _tracer = provider.get_tracer("lantern")
    return _tracer


@contextlib.contextmanager
def span(name: str, **attrs: Any) -> Iterator[ot.Span]:
    """A span; nested spans (and every chat call inside) become its children."""
    with tracer().start_as_current_span(name) as s:
        for k, v in attrs.items():
            if v is not None:
                s.set_attribute(k, v)
        yield s


def request_attrs(provider: str, model: str, s: dict[str, Any]) -> dict[str, Any]:
    return {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": provider,
        "gen_ai.request.model": model,
        "gen_ai.request.temperature": float(s["temperature"]),
        "gen_ai.request.max_tokens": int(s["max_tokens"]),
        "gen_ai.request.seed": s["seed"],
    }


def set_response(sp: ot.Span, r: Reply) -> None:
    sp.set_attribute("gen_ai.response.model", r.model)
    sp.set_attribute("gen_ai.usage.input_tokens", r.prompt_tokens)
    sp.set_attribute("gen_ai.usage.output_tokens", r.output_tokens)
    sp.set_attribute("gen_ai.usage.cache_read.input_tokens", r.cached_tokens)
    if r.stop_reason:
        sp.set_attribute("gen_ai.response.finish_reasons", [r.stop_reason])
    sp.set_attribute("lantern.prompt.version", r.prompt_version)
    sp.set_attribute("lantern.attempts", r.attempts)
    if r.cost_usd is not None:
        sp.set_attribute("lantern.cost_usd", r.cost_usd)
