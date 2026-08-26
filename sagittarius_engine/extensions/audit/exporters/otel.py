"""OpenTelemetry exporter (`EPIC-005C`, requirement 3) — behind the `[otel]`
extra (requirement 4).

@par Why this is the exporter that matters
`EPIC-005` §5.1: for a framework aiming to be credible in professional use,
standard spans are worth more than any bespoke viewer. Jaeger, Tempo, Grafana
and Datadog are already running where this framework wants to be taken
seriously, and a bespoke UI is something a team must learn and has no reason
to trust.

@par The core still knows nothing about OTel
Importing `sagittarius_engine.extensions.audit` — or anything else in the
engine — never imports this module. `opentelemetry-sdk` is imported here,
guarded, at **use time**, not package import time, so uninstalling the
`[otel]` extra leaves every other exporter and the recorder itself working.
`OTEL_INSTALLED` is exposed so a caller can check before calling in rather
than catching an exception.

@par Reconstructing parent/child from a flat record stream
The recorder does not store a parent pointer — only a correlation id shared
by the records of one dispatch (`kernel/dispatcher.py`: total span, each
middleware frame, the handler span). That id is minted fresh per dispatch and
used only synchronously within that one call, so within one id group the
spans are **properly nested** (no partial overlaps) by construction: a span
opened later than another, while that other is still open, always closes
before it. That is exactly the invariant a stack-based sweep needs to
reconstruct the tree — see `_parents_within_group()`.

Records with `cid == 0` — extension boot spans, task-run spans, and
everything the application records through `ctx.trace` — carry no such
grouping. Each becomes an **independent single-span trace**. That is an
honest simplification, not an oversight: recorded here because a nicer
result (say, one shared "boot" trace for every extension span) is additional
design, not a bug in this one. See `EPIC-005B`'s own outcome note on
instrumentation coverage for the same kind of honesty about scope.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..contracts import Hello, RecordKind, TraceRecord

try:
    from opentelemetry.trace import Span, Tracer, TracerProvider, set_span_in_context

    OTEL_INSTALLED = True
except ImportError:
    OTEL_INSTALLED = False


class OTelNotInstalled(RuntimeError):
    """@brief Raised when this module is used without the `[otel]` extra.

    @details Not an `ImportError`: that exception is already meaningful
    elsewhere in this module (a genuinely broken environment), and conflating
    "you did not install the optional extra" with "something is wrong with
    your installation" would make the fix — `pip install
    "sagittarius-engine[otel]"` — harder to find in the traceback.
    """


def _require_otel() -> None:
    if not OTEL_INSTALLED:
        raise OTelNotInstalled(
            "the OpenTelemetry exporter needs the optional 'otel' extra: "
            'pip install "sagittarius-engine[otel]"'
        )


def replay_to_tracer_provider(
    hello: Hello, records: Iterable[TraceRecord], tracer_provider: "TracerProvider"
) -> int:
    """
    @brief Replays a recording into any configured `TracerProvider`.

    @details Deliberately generic over the processor/exporter the provider
    was built with — a `BatchSpanProcessor(OTLPSpanExporter(...))` to send to
    a real collector, or an in-memory exporter for a test. Wiring OTLP is
    ordinary OTel SDK configuration; this function's only job is producing
    correct spans, not speaking the OTLP wire protocol.

    @param hello Anchors monotonic offsets to wall-clock time: OTel wants
        epoch nanoseconds, the recorder only ever measured elapsed ones.
    @return The number of genuinely still-open spans — a begin marker with no
        matching end anywhere in `records`. No end time exists to give one of
        these an OTel span, and none ever will for a recording already saved
        and now being replayed — dropped, not guessed at, the same rule the
        Perfetto encoder applies to the identical case. Returned rather than
        logged so a caller can decide whether a non-zero count matters to
        them.

        @warning This is **not** a count of `dur == 0` records. Every closed
        span has exactly one such record — `span_begin()` always writes one,
        by design (`recorder.py`) — so counting them directly would report
        "5 unclosed" on a perfectly clean, fully-stopped application. Found
        by running a real dispatch through this function and reading the
        number, not by reasoning about the code: a first version did exactly
        that and was wrong on every call. See `_count_unclosed()`.
    """
    _require_otel()
    records = tuple(records)
    tracer = tracer_provider.get_tracer("sagittarius-engine")

    closed_spans = [r for r in records if r.kind is RecordKind.SPAN and r.dur > 0]
    unclosed = _count_unclosed(records)

    grouped: dict[int, list[TraceRecord]] = {}
    for span in closed_spans:
        grouped.setdefault(span.cid, []).append(span)

    for cid, group in grouped.items():
        if cid == 0:
            for span in group:
                _emit_root(tracer, hello, span)
        else:
            _emit_group(tracer, hello, group)

    for record in records:
        if record.kind is RecordKind.INSTANT and record.cid == 0:
            _emit_orphan_instant(tracer, hello, record)

    return unclosed


def _count_unclosed(records: tuple[TraceRecord, ...]) -> int:
    """
    @brief How many begin markers have no matching end anywhere in `records`.

    @details A begin marker and its end marker share `(lane, name, cat, cid)`
    — every instrumentation site passes the same four values to both
    `span_begin()` and `span_end()`. That is not a unique key on its own (the
    same handler dispatched twice with `cid=0` produces two begin markers and
    two end markers under one key), so pairing is done by **count**, per key,
    rather than by identity: `max(0, begins - ends)` is the number of that
    key's begin markers that cannot possibly have a partner, regardless of
    which specific one it would be. That is all the caller needs — *how
    many*, not *which*.
    """
    begins: dict[tuple[Any, ...], int] = {}
    ends: dict[tuple[Any, ...], int] = {}
    for record in records:
        if record.kind is not RecordKind.SPAN:
            continue
        key = (record.lane, record.name, record.cat, record.cid)
        bucket = begins if record.dur == 0 else ends
        bucket[key] = bucket.get(key, 0) + 1

    return sum(max(0, count - ends.get(key, 0)) for key, count in begins.items())


def _wall_ns(hello: Hello, monotonic_offset_ns: int) -> int:
    """@brief The mapping table's rule, in one place: `start_time`/`end_time`
    come from the monotonic clock, anchored to the wall-clock epoch."""
    return hello.epoch_wall_ns + monotonic_offset_ns


def _attributes(record: TraceRecord) -> dict[str, Any]:
    """@brief `args` → span attributes, per the mapping table. OTel attributes
    must be primitives or primitive sequences; this engine's `args` already
    are, by the same constraint the wire protocol places on them."""
    return dict(record.args) if record.args else {}


def _emit_root(tracer: "Tracer", hello: Hello, span: TraceRecord) -> None:
    """@brief A `cid == 0` span: no parent, no children, its own trace."""
    end_ns = _wall_ns(hello, span.t)
    start_ns = end_ns - span.dur
    otel_span = tracer.start_span(
        span.name, start_time=start_ns, attributes=_attributes(span)
    )
    otel_span.end(end_time=end_ns)


def _emit_orphan_instant(tracer: "Tracer", hello: Hello, instant: TraceRecord) -> None:
    """@brief A `cid == 0` instant, with nothing to attach it to.

    @details Given no enclosing span, it becomes a single-point span (start
    == end) carrying one event of the same name — the mapping table's
    "instant → span event" rule, kept true even for the orphan case rather
    than silently dropping it. The cost is visible in a backend as its own
    tiny trace per marker; a caller who wants marks nested under real work
    should wrap them in `ctx.trace.span(...)`, which shares no grouping with
    this path today (see the module docstring).
    """
    at_ns = _wall_ns(hello, instant.t)
    otel_span = tracer.start_span(instant.name, start_time=at_ns)
    otel_span.add_event(instant.name, attributes=_attributes(instant), timestamp=at_ns)
    otel_span.end(end_time=at_ns)


def _emit_group(tracer: "Tracer", hello: Hello, group: list[TraceRecord]) -> None:
    """@brief One `cid` group — real parent/child structure, reconstructed by
    interval containment and emitted in an order that lets each child find
    its already-created parent span."""
    parent_of = _parents_within_group(group)

    # Parents must exist before `set_span_in_context()` can point a child at
    # them, so process outermost-first: a span with no parent, or whose
    # parent is already emitted, is ready.
    order = sorted(group, key=lambda s: (s.t - s.dur, -s.t))
    otel_spans: dict[int, "Span"] = {}

    for record in order:
        parent_record = parent_of[id(record)]
        context = (
            set_span_in_context(otel_spans[id(parent_record)])
            if parent_record is not None
            else None
        )
        end_ns = _wall_ns(hello, record.t)
        start_ns = end_ns - record.dur
        otel_span = tracer.start_span(
            record.name,
            context=context,
            start_time=start_ns,
            attributes=_attributes(record),
        )
        otel_spans[id(record)] = otel_span

    # Ended in reverse — innermost first — matching how the engine itself
    # closes spans (LIFO, via `finally`). Not required by the SDK, which
    # accepts `end()` in any order, but it keeps the replay's own event order
    # honest with respect to the run it is replaying.
    for record in reversed(order):
        end_ns = _wall_ns(hello, record.t)
        otel_spans[id(record)].end(end_time=end_ns)


def build_otlp_tracer_provider(
    endpoint: str | None = None, *, service_name: str = "sagittarius-engine"
) -> "TracerProvider":
    """
    @brief Convenience: a `TracerProvider` wired to export over OTLP/HTTP.

    @details Ordinary OTel SDK setup — a `Resource`, a
    `BatchSpanProcessor(OTLPSpanExporter(...))` — offered here only so a
    caller does not have to know that recipe to try the exporter against a
    local collector. Nothing about `replay_to_tracer_provider()` depends on
    this function; any `TracerProvider`, however built, works with it.

    @param endpoint The collector's OTLP/HTTP traces endpoint, e.g.
        `"http://localhost:4318/v1/traces"`. `None` uses the exporter's own
        default, which is that same local address — the standard target for
        "a local OTLP collector" in `EPIC-005C`'s own requirement 3.
    """
    _require_otel()
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = SdkTracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    exporter_kwargs = {"endpoint": endpoint} if endpoint else {}
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(**exporter_kwargs)))
    return provider


def _parents_within_group(
    group: list[TraceRecord],
) -> dict[int, TraceRecord | None]:
    """
    @brief Stack-based interval sweep: for each span, its parent is the
    innermost still-open span when it starts.

    @details Relies on proper nesting — no partial overlaps — which holds
    within one correlation id because that id is minted once per dispatch and
    used synchronously by that one call chain (see the module docstring).
    Sorted by start ascending, and by *end descending* as the tie-break: if
    two spans start at the same instant (possible at the clock's ~1 µs
    resolution — `EPIC-005A`'s `Hello.clock_resolution_ns`), the one that
    lasts longer is the outer one.

    @return Keyed by `id(record)`, not by any field on `TraceRecord` — the
    dataclass is frozen but not guaranteed hashable-by-identity-only, and two
    spans of the same handler can otherwise compare equal.
    """
    ordered = sorted(group, key=lambda s: (s.t - s.dur, -s.t))
    stack: list[TraceRecord] = []
    parent_of: dict[int, TraceRecord | None] = {}

    for record in ordered:
        start = record.t - record.dur
        while stack and (stack[-1].t) <= start:
            stack.pop()
        parent_of[id(record)] = stack[-1] if stack else None
        stack.append(record)

    return parent_of
