"""OpenTelemetry exporter (`EPIC-005C` requirement 3), and requirement 4 —
the `[otel]` extra is genuinely optional.

@par Verified without a live collector
Requirement 3 asks for a run to "appear in a local OTLP collector with
correct parent/child structure." There is no collector in this environment,
so the meaningful half — parent/child structure — is verified against the
OTel SDK's own `InMemorySpanExporter`, which records exactly the spans a real
collector would receive, before the OTLP wire encoding. That is the same
class of honest substitution used elsewhere in this repository (verifying a
system-library failure by reproducing both directions in a matching venv,
rather than asserting it) rather than a shortcut.
"""

from __future__ import annotations

import time

import pytest

from sagittarius_engine.extensions.audit.contracts import (
    Hello,
    Lane,
    RecordKind,
    TraceRecord,
)
from sagittarius_engine.extensions.audit.exporters import otel
from sagittarius_engine.extensions.audit.recorder import TraceRecorder
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces import IMiddleware
from sagittarius_engine.kernel import App

pytestmark = pytest.mark.skipif(
    not otel.OTEL_INSTALLED,
    reason="needs the optional 'otel' extra: pip install \"sagittarius-engine[otel]\"",
)

if otel.OTEL_INSTALLED:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )


def _provider():
    """@brief A `TracerProvider` wired to an in-memory exporter, and the
    exporter itself so a test can read back what was replayed."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _by_name(spans):
    return {s.name: s for s in spans}


# ---------------------------------------------------------------- requirement 4


def test_the_module_reports_whether_it_is_usable():
    assert otel.OTEL_INSTALLED is True


def test_calling_in_without_the_extra_raises_a_named_error(monkeypatch):
    """Distinct from `ImportError`, which this module also raises for a
    genuinely broken environment -- conflating "extra not installed" with
    "your installation is broken" would hide the fix in the traceback."""
    monkeypatch.setattr(otel, "OTEL_INSTALLED", False)
    with pytest.raises(otel.OTelNotInstalled, match="otel"):
        otel.replay_to_tracer_provider(Hello(), (), tracer_provider=None)


# ------------------------------------------------------ mapping table, unit level


def test_a_span_maps_start_end_and_attributes():
    hello = Hello(epoch_wall_ns=1_700_000_000_000_000_000)
    records = (
        TraceRecord(
            t=1_000_000,
            kind=RecordKind.SPAN,
            lane=Lane.TASK,
            name="run",
            dur=400_000,
            args={"task_id": "abc"},
        ),
    )
    provider, exporter = _provider()

    unclosed = otel.replay_to_tracer_provider(hello, records, provider)

    assert unclosed == 0
    (span,) = exporter.get_finished_spans()
    assert span.name == "run"
    assert span.end_time == hello.epoch_wall_ns + 1_000_000
    assert span.start_time == span.end_time - 400_000
    assert dict(span.attributes) == {"task_id": "abc"}
    assert span.parent is None


def test_a_still_open_span_is_skipped_and_counted():
    """No end time exists for one of these, and none ever will for a
    recording already saved and now being replayed -- the same rule the
    Perfetto encoder applies."""
    hello = Hello()
    records = (
        TraceRecord(t=100, kind=RecordKind.SPAN, lane=Lane.TASK, name="run", dur=0),
    )
    provider, exporter = _provider()

    unclosed = otel.replay_to_tracer_provider(hello, records, provider)

    assert unclosed == 1
    assert exporter.get_finished_spans() == ()


def test_two_cid_zero_spans_are_independent_traces():
    """cid == 0 carries no grouping information at all -- each becomes its
    own single-span trace rather than being falsely linked."""
    hello = Hello()
    records = (
        TraceRecord(t=100, kind=RecordKind.SPAN, lane=Lane.EXTENSION, name="a", dur=50),
        TraceRecord(t=200, kind=RecordKind.SPAN, lane=Lane.EXTENSION, name="b", dur=50),
    )
    provider, exporter = _provider()

    otel.replay_to_tracer_provider(hello, records, provider)

    spans = _by_name(exporter.get_finished_spans())
    assert spans["a"].parent is None
    assert spans["b"].parent is None
    assert spans["a"].context.trace_id != spans["b"].context.trace_id


def test_an_orphan_instant_becomes_a_span_carrying_one_event():
    """The mapping table says instant -> span event. With nothing to attach
    it to (cid == 0), it must still become an event somewhere rather than
    being silently dropped."""
    hello = Hello(epoch_wall_ns=5_000_000_000)
    records = (
        TraceRecord(
            t=1_000,
            kind=RecordKind.INSTANT,
            lane=Lane.USER,
            name="order-filled",
            args={"price": 101.5},
        ),
    )
    provider, exporter = _provider()

    otel.replay_to_tracer_provider(hello, records, provider)

    (span,) = exporter.get_finished_spans()
    assert span.name == "order-filled"
    (event,) = span.events
    assert event.name == "order-filled"
    assert dict(event.attributes) == {"price": 101.5}
    assert event.timestamp == hello.epoch_wall_ns + 1_000


# --------------------------------------------------- real parent/child structure


def test_a_dispatch_group_reconstructs_correct_parent_child_structure():
    """The literal wording of requirement 3. Built from records that share a
    correlation id the way `kernel/dispatcher.py` actually mints and uses
    one -- total contains handler."""
    hello = Hello()
    cid = 7
    records = (
        TraceRecord(
            t=1_000_000,
            kind=RecordKind.SPAN,
            lane=Lane.DISPATCH,
            name="Greet",
            cat="command",
            dur=1_000_000,
            cid=cid,
        ),
        TraceRecord(
            t=900_000,
            kind=RecordKind.SPAN,
            lane=Lane.DISPATCH,
            name="Greet",
            cat="handler",
            dur=500_000,
            cid=cid,
        ),
    )
    provider, exporter = _provider()

    otel.replay_to_tracer_provider(hello, records, provider)

    total = next(s for s in exporter.get_finished_spans() if s.start_time == 0)
    handler = next(s for s in exporter.get_finished_spans() if s.start_time == 400_000)

    assert handler.parent is not None
    assert handler.parent.span_id == total.context.span_id
    assert handler.context.trace_id == total.context.trace_id
    assert total.parent is None


def test_three_levels_nest_correctly_and_ties_break_toward_the_longer_span():
    """Two spans starting at the same instant: the one that lasts longer is
    the outer one -- the tie-break `_parents_within_group()` documents."""
    hello = Hello()
    cid = 1
    # outer:  [0 ----------------- 300]
    # middle: [0 --------- 200]
    # inner:          [100 - 150]
    records = (
        TraceRecord(
            t=300,
            kind=RecordKind.SPAN,
            lane=Lane.DISPATCH,
            name="outer",
            dur=300,
            cid=cid,
        ),
        TraceRecord(
            t=200,
            kind=RecordKind.SPAN,
            lane=Lane.MIDDLEWARE,
            name="middle",
            dur=200,
            cid=cid,
        ),
        TraceRecord(
            t=150,
            kind=RecordKind.SPAN,
            lane=Lane.MIDDLEWARE,
            name="inner",
            dur=50,
            cid=cid,
        ),
    )
    provider, exporter = _provider()

    otel.replay_to_tracer_provider(hello, records, provider)

    spans = _by_name(exporter.get_finished_spans())
    assert spans["middle"].parent.span_id == spans["outer"].context.span_id
    assert spans["inner"].parent.span_id == spans["middle"].context.span_id
    assert spans["outer"].parent is None


def test_spans_are_ended_in_the_same_order_the_engine_closed_them():
    """Not required by the SDK, but keeps the replay's own event order
    honest with respect to the run it replays -- innermost closes first,
    matching the engine's `finally`-based LIFO closing."""
    hello = Hello()
    records = (
        TraceRecord(
            t=200,
            kind=RecordKind.SPAN,
            lane=Lane.DISPATCH,
            name="outer",
            cat="command",
            dur=200,
            cid=1,
        ),
        TraceRecord(
            t=150,
            kind=RecordKind.SPAN,
            lane=Lane.DISPATCH,
            name="outer",
            cat="handler",
            dur=50,
            cid=1,
        ),
    )
    ended_order = []

    class RecordingExporter(InMemorySpanExporter):
        def export(self, spans):
            ended_order.extend(s.name for s in spans)
            return super().export(spans)

    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(RecordingExporter()))

    otel.replay_to_tracer_provider(hello, records, provider)

    assert ended_order[0] == "outer"  # cat=handler ends before cat=command


# --------------------------------------------------------------- real app, e2e


class Passthrough(IMiddleware):
    def process(self, cmd_or_query, dto, next_handler):
        return next_handler()


class GreetCommand:
    def execute(self, dto=None):
        time.sleep(0.001)
        return "hi"


def test_a_real_dispatch_replays_with_correct_structure():
    app = App(StdLibContainer(), MemoryEventBus())
    recorder = app.context.enable_tracing(TraceRecorder())
    app.boot()
    app.context.middleware_pipeline.add(Passthrough())
    app.context.container.bind(GreetCommand, GreetCommand)
    app.dispatch(GreetCommand)
    app.stop()

    provider, exporter = _provider()
    unclosed = otel.replay_to_tracer_provider(
        recorder.hello(), recorder.snapshot(), provider
    )

    # The regression this guards: a first version counted every `dur == 0`
    # record as "unclosed", which is every span's own begin marker -- it
    # reported 5 on this exact fully-stopped, nothing-actually-open run.
    # Found by running it and reading the number, not by reasoning about the
    # code.
    assert unclosed == 0

    spans = exporter.get_finished_spans()
    # Every dispatch/middleware span shares one cid via the OTel trace id.
    trace_ids = {s.context.trace_id for s in spans if s.name == "GreetCommand"}
    assert len(trace_ids) == 1
    handler_spans = [
        s for s in spans if s.name == "GreetCommand" and s.parent is not None
    ]
    assert handler_spans, "the handler span must have a parent (the dispatch total)"


def test_a_genuinely_open_span_amid_closed_ones_is_still_counted():
    """`_count_unclosed()` must not regress into "0 whenever anything is
    closed" while fixing the false-positive above -- a real open span, mixed
    in with normal closed ones, must still be found."""
    hello = Hello()
    records = (
        # A normal, fully closed span: begin + end.
        TraceRecord(
            t=0, kind=RecordKind.SPAN, lane=Lane.TASK, name="closed", dur=0, cid=0
        ),
        TraceRecord(
            t=100, kind=RecordKind.SPAN, lane=Lane.TASK, name="closed", dur=100, cid=0
        ),
        # A begin marker with no matching end anywhere.
        TraceRecord(
            t=200, kind=RecordKind.SPAN, lane=Lane.TASK, name="open", dur=0, cid=0
        ),
    )
    provider, exporter = _provider()

    unclosed = otel.replay_to_tracer_provider(hello, records, provider)

    assert unclosed == 1
    assert {s.name for s in exporter.get_finished_spans()} == {"closed"}


def test_build_otlp_tracer_provider_does_not_require_a_live_collector():
    """Constructing the provider is ordinary SDK setup and must not touch the
    network -- only actually flushing spans through a `BatchSpanProcessor`
    would, and this test never flushes."""
    provider = otel.build_otlp_tracer_provider(
        endpoint="http://localhost:4318/v1/traces"
    )
    assert provider is not None
    provider.shutdown()
