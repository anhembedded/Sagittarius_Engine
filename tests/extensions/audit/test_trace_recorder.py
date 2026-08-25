"""`EPIC-005A` — protocol v1 and the ring-buffer recorder.

The overhead budget is tested here rather than left to a benchmark script,
because this milestone's "Risk to watch" makes it an *acceptance criterion*: a
tracer that perturbs what it measures is worse than none, and discovering that
after `EPIC-005B`'s instrumentation is written against it means rewriting every
instrumentation site.
"""

from __future__ import annotations

import json
import sys
import timeit

import pytest

from sagittarius_engine.extensions.audit.contracts import (
    PROTOCOL_VERSION,
    Envelope,
    Hello,
    Lane,
    MessageType,
    ProtocolMismatch,
    RecordKind,
    TraceRecord,
    check_protocol,
    error_message,
    trace_batch,
)
from sagittarius_engine.extensions.audit.recorder import TraceRecorder


@pytest.fixture
def recorder():
    return TraceRecorder(capacity=16)


# --------------------------------------------------------------- the contract


def test_a_record_survives_a_round_trip_through_the_wire_shape():
    original = TraceRecord(
        t=123,
        kind=RecordKind.SPAN,
        lane=Lane.TASK,
        name="task.run",
        cat="worker",
        cid=7,
        dur=4_000,
        args={"symbol": "BTC"},
    )
    assert TraceRecord.from_dict(original.to_dict()) == original


def test_empty_and_zero_fields_are_left_off_the_wire():
    """On a 10k-events/sec stream, the difference between sending `"c": ""` and
    sending nothing is most of the bandwidth."""
    minimal = TraceRecord(t=1, kind=RecordKind.INSTANT, lane=Lane.KERNEL, name="boot")

    assert minimal.to_dict() == {"t": 1, "k": "i", "l": "kernel", "n": "boot"}
    assert TraceRecord.from_dict(minimal.to_dict()) == minimal


def test_the_wire_shape_is_json_serialisable_with_no_custom_encoder():
    """`StrEnum` values, not enum objects — a consumer in another process must
    be able to `json.loads` this without importing anything of ours."""
    record = TraceRecord(t=1, kind=RecordKind.SPAN, lane=Lane.USER, name="x")
    assert json.loads(json.dumps(record.to_dict()))["l"] == "user"


def test_a_version_mismatch_fails_loudly_rather_than_degrading():
    """D1 is what tolerating a mismatch looks like: a blank panel that reads as
    'nothing is happening'."""
    check_protocol(PROTOCOL_VERSION)  # must not raise

    with pytest.raises(ProtocolMismatch) as excinfo:
        check_protocol(PROTOCOL_VERSION + 1)
    assert str(PROTOCOL_VERSION + 1) in str(excinfo.value)
    assert str(PROTOCOL_VERSION) in str(excinfo.value)


def test_an_envelope_from_a_future_version_is_refused_before_it_is_parsed():
    payload = {"v": PROTOCOL_VERSION + 99, "type": "trace", "seq": 1, "data": []}
    with pytest.raises(ProtocolMismatch):
        Envelope.from_dict(payload)


def test_a_trace_batch_is_one_message_not_one_per_record():
    records = tuple(
        TraceRecord(t=i, kind=RecordKind.INSTANT, lane=Lane.EVENT_BUS, name="e")
        for i in range(100)
    )
    envelope = trace_batch(seq=3, records=records)

    assert envelope.type is MessageType.TRACE
    assert len(envelope.data) == 100
    assert Envelope.from_dict(envelope.to_dict()).seq == 3


def test_an_error_is_a_message_type_not_a_swallowed_log_line():
    """The old implementation had eleven bare `except Exception: logger.error`
    blocks and the consumer just saw a field go missing."""
    envelope = error_message(seq=1, detail="broadcaster failed to bind")
    assert envelope.type is MessageType.ERROR
    assert "bind" in envelope.data["detail"]


def test_hello_round_trips_and_carries_the_lane_table():
    hello = Hello(epoch_wall_ns=1700, capacity=1024, dropped_before_connect=5)
    restored = Hello.from_dict(hello.to_dict())

    assert restored == hello
    assert "task" in restored.lanes


# ----------------------------------------------------------------- capturing


def test_an_instant_is_captured_with_a_monotonic_offset(recorder):
    recorder.instant(Lane.KERNEL, "app.boot")
    (record,) = recorder.snapshot()

    assert record.kind is RecordKind.INSTANT
    assert record.lane is Lane.KERNEL
    assert record.name == "app.boot"
    assert record.t >= 0
    assert record.dur == 0


def test_a_span_records_a_duration(recorder):
    started = recorder.span_begin(Lane.TASK, "task.run", cid=1)
    recorder.span_end(Lane.TASK, "task.run", started, cid=1)

    begin, end = recorder.snapshot()
    assert begin.dur == 0
    assert end.dur > 0
    assert begin.cid == end.cid == 1


def test_the_recorder_row_and_the_contract_agree_on_field_order():
    """`from_row()` unpacks a fixed 8-tuple. The two modules must agree, and a
    silent reordering would mis-label every field rather than raise."""
    rec = TraceRecorder(capacity=4)
    rec.instant(Lane.MIDDLEWARE, "frame", cat="timing", cid=9, args={"k": "v"})

    (record,) = rec.snapshot()
    assert (record.lane, record.name, record.cat, record.cid, record.args) == (
        Lane.MIDDLEWARE,
        "frame",
        "timing",
        9,
        {"k": "v"},
    )


# -------------------------------------------------------- bounded, and honest


def test_the_buffer_evicts_oldest_first_and_never_grows(recorder):
    for i in range(100):
        recorder.instant(Lane.USER, f"marker-{i}")

    retained = recorder.snapshot()
    assert len(retained) == 16, "capacity was not respected"
    assert retained[0].name == "marker-84", "eviction was not oldest-first"
    assert retained[-1].name == "marker-99"


def test_every_evicted_record_is_counted(recorder):
    """A `deque(maxlen=...)` discards silently. A trace with unreported holes is
    worse than a short one, because it looks complete."""
    for i in range(20):
        recorder.instant(Lane.USER, f"marker-{i}")

    assert recorder.dropped == 4
    assert recorder.hello().dropped_before_connect == 4


def test_nothing_is_dropped_while_there_is_room(recorder):
    for i in range(16):
        recorder.instant(Lane.USER, f"marker-{i}")
    assert recorder.dropped == 0


# ------------------------------------------------------------------ draining


def test_snapshot_does_not_consume(recorder):
    """Retained mode: a consumer attaching late reads what already happened
    without taking it away from the next one."""
    recorder.instant(Lane.USER, "marker")

    assert len(recorder.snapshot()) == 1
    assert len(recorder.snapshot()) == 1


def test_drain_consumes_oldest_first(recorder):
    for i in range(5):
        recorder.instant(Lane.USER, f"marker-{i}")

    first = recorder.drain(limit=2)
    assert [r.name for r in first] == ["marker-0", "marker-1"]
    assert len(recorder) == 3


def test_a_record_arriving_mid_drain_is_not_lost(recorder):
    """`popleft()` in a loop rather than copy-then-clear: with the latter, an
    append landing between the copy and the clear is silently discarded."""
    for i in range(4):
        recorder.instant(Lane.USER, f"old-{i}")

    recorder.drain(limit=2)
    recorder.instant(Lane.USER, "new")

    assert [r.name for r in recorder.snapshot()] == ["old-2", "old-3", "new"]


def test_correlation_ids_are_unique(recorder):
    assert len({recorder.next_cid() for _ in range(100)}) == 100


def test_clear_resets_the_buffer_and_the_drop_count(recorder):
    for i in range(20):
        recorder.instant(Lane.USER, f"marker-{i}")
    recorder.clear()

    assert len(recorder) == 0
    assert recorder.dropped == 0


# ---------------------------------------------- the acceptance criterion (4.2)

#: Deliberately loose against the 157 ns measured on a quiet machine. CI runners
#: are shared and variable, and a benchmark assertion tight enough to catch a
#: 20% regression would fail on load instead — which trains people to ignore it.
#: This catches the regression that matters: an accidental `str()`, `repr()` or
#: dataclass construction on the capture path, each of which costs microseconds,
#: not nanoseconds.
_ENABLED_BUDGET_NS = 2_000


def _ns_per_call(fn, number: int = 20_000) -> float:
    return min(timeit.repeat(fn, number=number, repeat=3)) / number * 1e9


def _instrumentation() -> str:
    """@brief Names whatever is tracing this process, or `""`.

    Coverage, a profiler and a debugger all install a trace hook that fires per
    line, which makes any timing measurement meaningless.
    """
    hook = sys.gettrace()
    if hook is not None:
        return type(hook).__module__.split(".")[0]
    monitoring = getattr(sys, "monitoring", None)
    if monitoring is not None:
        for tool_id in range(6):
            name = monitoring.get_tool(tool_id)
            if name:
                return name
    return ""


#: The two tests below are timing measurements, and CI's `test` job runs
#: `pytest --cov`, whose per-line trace hook takes a 157 ns trace point to
#: **2407 ns** — over budget by itself, with nothing wrong. Left unguarded they
#: would be permanently red in CI while the code was correct, which is exactly
#: the "a test that could never pass in CI" fault `TASK-040` found and fixed.
#:
#: So they skip under instrumentation and run in the `benchmark` job, which does
#: not use `--cov`. That job is wired to run this file (`TASK-020` is the
#: cautionary tale about a benchmark job nobody reads); if it is ever dropped,
#: these acceptance criteria stop being checked anywhere.
_INSTRUMENTED = _instrumentation()
_needs_a_quiet_process = pytest.mark.skipif(
    bool(_INSTRUMENTED),
    reason=(
        f"timing measurement is meaningless under {_INSTRUMENTED!r} — "
        "run via the benchmark job, which does not use --cov"
    ),
)


@_needs_a_quiet_process
def test_an_enabled_trace_point_stays_inside_the_overhead_budget():
    """`EPIC-005` §4.2's budget, as a test rather than a claim in a document."""
    recorder = TraceRecorder(capacity=100_000)
    per_call = _ns_per_call(lambda: recorder.instant(Lane.TASK, "task.run", cid=1))

    assert per_call < _ENABLED_BUDGET_NS, (
        f"a trace point costs {per_call:.0f} ns, over the {_ENABLED_BUDGET_NS} ns "
        "budget — something on the capture path is formatting or allocating"
    )


@_needs_a_quiet_process
def test_the_disabled_path_is_a_guard_not_a_null_object():
    """The correction §4.2 records: measured, `if self._trace is not None` costs
    ~3 ns over an empty call site while a no-op object costs ~27 ns. This test
    locks in the *shape* — that a disabled site is cheaper than an enabled one
    by a wide margin — rather than a machine-specific figure."""

    class Site:
        __slots__ = ("_trace",)

        def __init__(self, trace):
            self._trace = trace

        def run(self):
            if self._trace is not None:
                self._trace.instant(Lane.TASK, "task.run")

    enabled = _ns_per_call(Site(TraceRecorder(capacity=100_000)).run)
    disabled = _ns_per_call(Site(None).run)

    assert disabled < enabled / 2, (
        f"disabled {disabled:.0f} ns vs enabled {enabled:.0f} ns — the guard is "
        "not short-circuiting, so a disabled build is paying for capture"
    )
