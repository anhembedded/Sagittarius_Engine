"""Perfetto exporter (`EPIC-005C` requirement 2).

`EPIC-005` §5's whole argument for building this before any UI is that
Perfetto validates the trace model against a viewer nobody here wrote. This
suite cannot literally open `ui.perfetto.dev` — there is no browser in this
environment — so it validates the same thing a browser would check: every
event is well-formed Chrome Trace Event Format, and spans that should nest by
construction (a middleware frame inside the dispatch it belongs to) really do
sit inside their parent's time interval, which is what Perfetto's own importer
relies on to draw the nesting at all.
"""

from __future__ import annotations

import time

from sagittarius_engine.extensions.audit.contracts import (
    Lane,
    RecordKind,
    TraceRecord,
)
from sagittarius_engine.extensions.audit.exporters.perfetto import (
    to_perfetto_trace,
    write_perfetto_trace,
)
from sagittarius_engine.extensions.audit.recorder import TraceRecorder
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces import IExtension, IMiddleware
from sagittarius_engine.kernel import App


def _events(trace: dict, ph: str) -> list[dict]:
    return [e for e in trace["traceEvents"] if e["ph"] == ph]


# ------------------------------------------------------------- unit-level


def test_a_closed_span_becomes_a_complete_event_with_the_right_interval():
    records = (
        TraceRecord(t=1_000, kind=RecordKind.SPAN, lane=Lane.TASK, name="run", dur=400),
    )
    trace = to_perfetto_trace(records)

    (event,) = _events(trace, "X")
    assert event["name"] == "run"
    # ts/dur are in microseconds; the record is in nanoseconds (t=end, dur).
    assert event["ts"] == (1_000 - 400) / 1000
    assert event["dur"] == 400 / 1000


def test_a_still_open_span_is_skipped_not_guessed_at():
    """A `SPAN` record with `dur == 0` is a begin marker with no end yet --
    there is no interval to draw, so it must not become a zero-length event."""
    records = (
        TraceRecord(t=100, kind=RecordKind.SPAN, lane=Lane.TASK, name="run", dur=0),
    )
    trace = to_perfetto_trace(records)

    assert _events(trace, "X") == []


def test_an_instant_becomes_a_thread_scoped_instant_event():
    records = (
        TraceRecord(
            t=250,
            kind=RecordKind.INSTANT,
            lane=Lane.USER,
            name="order-filled",
            args={"price": 101.5},
        ),
    )
    trace = to_perfetto_trace(records)

    (event,) = _events(trace, "i")
    assert event["name"] == "order-filled"
    assert event["ts"] == 250 / 1000
    assert event["s"] == "t"
    assert event["args"] == {"price": 101.5}


def test_only_lanes_that_actually_appear_get_a_thread_name():
    """An application using three of nine lanes should get three rows in
    Perfetto, not nine mostly-empty ones."""
    records = (
        TraceRecord(t=1, kind=RecordKind.INSTANT, lane=Lane.USER, name="a"),
        TraceRecord(t=2, kind=RecordKind.INSTANT, lane=Lane.TASK, name="b"),
    )
    trace = to_perfetto_trace(records)

    named_lanes = {
        e["args"]["name"] for e in _events(trace, "M") if e["name"] == "thread_name"
    }
    assert named_lanes == {"user", "task"}


def test_lane_track_ids_are_stable_across_two_exports():
    """Comparing two traces side by side in Perfetto only works if the same
    subsystem lands on the same track number both times."""
    a = to_perfetto_trace(
        (TraceRecord(t=1, kind=RecordKind.INSTANT, lane=Lane.TASK, name="x"),)
    )
    b = to_perfetto_trace(
        (
            TraceRecord(t=1, kind=RecordKind.INSTANT, lane=Lane.USER, name="y"),
            TraceRecord(t=2, kind=RecordKind.INSTANT, lane=Lane.TASK, name="x"),
        )
    )
    tid_a = next(e["tid"] for e in _events(a, "i") if e["name"] == "x")
    tid_b = next(e["tid"] for e in _events(b, "i") if e["name"] == "x")
    assert tid_a == tid_b


def test_write_perfetto_trace_produces_valid_json(tmp_path):
    path = tmp_path / "trace.json"
    write_perfetto_trace(
        str(path),
        (TraceRecord(t=1, kind=RecordKind.INSTANT, lane=Lane.USER, name="a"),),
    )

    import json

    assert "traceEvents" in json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------- end-to-end, real app


class SlowExtension(IExtension):
    name = "slow"

    def __init__(self) -> None:
        self.dependencies: list[str] = []

    def register(self, context) -> None: ...
    def boot(self, context) -> None:
        time.sleep(0.01)

    def shutdown(self, context) -> None: ...


class Passthrough(IMiddleware):
    def process(self, cmd_or_query, dto, next_handler):
        return next_handler()


class GreetCommand:
    def execute(self, dto=None):
        return "hi"


def test_a_real_apps_dispatch_nests_correctly_in_the_exported_trace():
    """The structural stand-in for "opens in ui.perfetto.dev with correct
    lanes and nested spans": every child interval must sit inside its
    parent's, because that containment is what the importer's own nesting
    algorithm depends on to draw a flame graph at all."""
    app = App(StdLibContainer(), MemoryEventBus())
    recorder = app.context.enable_tracing(TraceRecorder())
    app.use(SlowExtension())
    app.boot()
    app.context.middleware_pipeline.add(Passthrough())
    app.context.container.bind(GreetCommand, GreetCommand)
    app.dispatch(GreetCommand)
    app.stop()

    trace = to_perfetto_trace(recorder.snapshot())
    spans = _events(trace, "X")
    assert len(spans) >= 3  # extension start, dispatch total, handler (+middleware)

    by_lane: dict[int, list[dict]] = {}
    for span in spans:
        by_lane.setdefault(span["tid"], []).append(span)

    # Within the DISPATCH lane, the "total" span must contain the "handler"
    # span -- that is the literal nesting Perfetto renders as a call stack.
    dispatch_tid = next(
        tid
        for tid, evs in by_lane.items()
        if any(e["cat"] in ("command", "handler") for e in evs)
    )
    total = next(e for e in by_lane[dispatch_tid] if e["cat"] == "command")
    handler = next(e for e in by_lane[dispatch_tid] if e["cat"] == "handler")

    assert total["ts"] <= handler["ts"]
    assert handler["ts"] + handler["dur"] <= total["ts"] + total["dur"]
    assert total["args"]["cid"] == handler["args"]["cid"]
