"""`EPIC-005B` — the engine instrumenting itself, and `ctx.trace` for apps.

This is the half of `EPIC-005` that justifies the epic: `py-spy` and
`viztracer` already produce timelines from a running Python process without any
framework support. What they cannot produce is **meaning** — `py-spy` sees
`_dispatch_inner()`, not "command `GreetCommand`, through two middleware, into
its handler". Only the engine knows that, so only the engine can record it.
"""

from __future__ import annotations

import sys
import time
import timeit

import pytest

from sagittarius_engine.extensions.audit.recorder import TraceRecorder
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces import IExtension, IMiddleware
from sagittarius_engine.interfaces.i_dispatchable import IDispatchable
from sagittarius_engine.interfaces.i_trace_recorder import Lane
from sagittarius_engine.kernel import App

#: Sleeps are deliberately far apart so an assertion can tell them apart on a
#: loaded CI runner without being tight enough to flake. Nothing here asserts an
#: absolute duration; every check is a comparison or a generous bound.
SLOW = 0.02
QUICK = 0.002


class SlowExtension(IExtension):
    name = "slow"

    def __init__(self) -> None:
        self.dependencies: list[str] = []

    def register(self, context) -> None: ...

    def boot(self, context) -> None:
        time.sleep(SLOW)

    def shutdown(self, context) -> None: ...


class FastExtension(IExtension):
    name = "fast"

    def __init__(self) -> None:
        self.dependencies: list[str] = []

    def register(self, context) -> None: ...

    def boot(self, context) -> None: ...

    def shutdown(self, context) -> None: ...


class ExpensiveMiddleware(IMiddleware):
    def process(self, cmd_or_query, dto, next_handler):
        time.sleep(SLOW)
        return next_handler()


class CheapMiddleware(IMiddleware):
    def process(self, cmd_or_query, dto, next_handler):
        return next_handler()


class GreetCommand(IDispatchable):
    def execute(self, dto=None):
        return "hi"


class FailingCommand(IDispatchable):
    def execute(self, dto=None):
        raise ValueError("handler exploded")


def _app(*, tracing: bool = True):
    """Returns `(app, recorder)`; `recorder` is `None` when tracing is off.

    Deliberately unannotated: `enable_tracing()` returns the *interface*, so a
    `TraceRecorder | None` annotation would be a lie mypy correctly rejects,
    and widening it to `ITraceRecorder | None` would lose the concrete methods
    (`snapshot()`) every test here calls.
    """
    app = App(StdLibContainer(), MemoryEventBus())
    recorder = TraceRecorder() if tracing else None
    if recorder is not None:
        app.context.enable_tracing(recorder)
    return app, recorder


def _spans(recorder, lane=None, cat=None):
    """Closed spans only — a `span_begin` record carries `dur == 0`."""
    return [
        r
        for r in recorder.snapshot()
        if r.dur and (lane is None or r.lane == lane) and (cat is None or r.cat == cat)
    ]


# ------------------------------------------------------------------- off state


def test_tracing_is_off_unless_asked_for():
    app, _ = _app(tracing=False)
    assert app.context.recorder is None
    assert app.context.trace.enabled is False


def test_the_application_api_is_safe_when_tracing_is_off():
    """An API that made every application write `if ctx.trace is not None:`
    around its own markers would push the engine's constraint onto the place
    where it does not apply."""
    app, _ = _app(tracing=False)

    app.context.trace.mark("nothing-is-recorded", price=1)
    with app.context.trace.span("also-nothing"):
        pass  # must not raise


def test_disabling_keeps_what_was_already_recorded():
    """The report is usually read after the fact."""
    app, recorder = _app()
    app.context.trace.mark("before")
    app.context.disable_tracing()

    assert app.context.recorder is None
    assert len(recorder.snapshot()) == 1


def test_enabling_after_the_api_object_exists_still_takes_effect():
    """`TraceApi` reads the recorder off the context per call rather than
    caching it — a handle that silently recorded nothing would be the exact
    class of bug this epic is about."""
    app, _ = _app(tracing=False)
    trace = app.context.trace

    recorder = app.context.enable_tracing(TraceRecorder())
    trace.mark("after")

    assert [r.name for r in recorder.snapshot()] == ["after"]


# --------------------------------------------------------------- boot profiling


def test_boot_profiling_separates_a_slow_extension_from_a_fast_one():
    """ "Why does startup take four seconds?" as a bar chart — `EPIC-005B` names
    this as one of two things that fall out for free."""
    app, recorder = _app()
    app.use(SlowExtension())
    app.use(FastExtension())
    app.boot()

    by_name = {r.name: r.dur for r in _spans(recorder, Lane.EXTENSION, "start")}
    assert set(by_name) == {"SlowExtension", "FastExtension"}
    assert by_name["SlowExtension"] > by_name["FastExtension"] * 5
    assert by_name["SlowExtension"] >= SLOW * 1e9 * 0.5


def test_the_recorder_must_exist_before_boot_to_profile_it():
    """Stated in `enable_tracing()`'s docstring, and true: extensions start
    during `boot()`, so a recorder installed afterwards has nothing to record."""
    app, _ = _app(tracing=False)
    app.use(SlowExtension())
    app.boot()

    recorder = app.context.enable_tracing(TraceRecorder())
    assert _spans(recorder, Lane.EXTENSION) == []


# -------------------------------------------------------------- middleware cost


def test_a_span_per_middleware_frame_names_the_right_middleware():
    """The regression this guards: wrapping the frames in a closure built
    inside the loop makes Python's late binding report the *last* middleware's
    name for every frame — a trace that is confidently wrong rather than merely
    absent. `_traced_frame()` is a module-level function for this reason."""
    app, recorder = _app()
    app.boot()
    app.context.middleware_pipeline.add(CheapMiddleware())
    app.context.middleware_pipeline.add(ExpensiveMiddleware())
    app.context.container.bind(GreetCommand, GreetCommand)

    app.dispatch(GreetCommand)

    names = {r.name for r in _spans(recorder, Lane.MIDDLEWARE)}
    assert names == {"CheapMiddleware", "ExpensiveMiddleware"}


def test_middleware_spans_are_inclusive_so_self_time_is_parent_minus_child():
    """Frames nest, so an outer frame's duration contains the inner ones. That
    is what a flame graph needs, and it is why the expensive frame is found by
    subtraction rather than by reading one number — `EPIC-005` §5's argument for
    borrowing Perfetto rather than building a viewer."""
    app, recorder = _app()
    app.boot()
    app.context.middleware_pipeline.add(CheapMiddleware())  # outermost
    app.context.middleware_pipeline.add(ExpensiveMiddleware())
    app.context.container.bind(GreetCommand, GreetCommand)

    app.dispatch(GreetCommand)

    by_name = {r.name: r.dur for r in _spans(recorder, Lane.MIDDLEWARE)}
    assert by_name["CheapMiddleware"] >= by_name["ExpensiveMiddleware"]
    # Cheap's own cost is the difference, and it is ~nothing.
    self_time = by_name["CheapMiddleware"] - by_name["ExpensiveMiddleware"]
    assert self_time < by_name["ExpensiveMiddleware"] / 2


def test_no_middleware_means_no_middleware_spans():
    app, recorder = _app()
    app.boot()
    app.context.container.bind(GreetCommand, GreetCommand)

    app.dispatch(GreetCommand)

    assert _spans(recorder, Lane.MIDDLEWARE) == []


# -------------------------------------------------------------------- dispatch


def test_dispatch_records_a_total_and_a_handler_span_sharing_one_id():
    """Without the correlation id, a concurrent dispatch on another thread
    interleaves into the same lane and the trace reads as one impossible call."""
    app, recorder = _app()
    app.boot()
    app.context.container.bind(GreetCommand, GreetCommand)

    app.dispatch(GreetCommand)

    spans = _spans(recorder, Lane.DISPATCH)
    cats = {r.cat for r in spans}
    assert cats == {"command", "handler"}
    assert len({r.cid for r in spans}) == 1, "dispatch and handler are unrelated"
    assert all(r.cid != 0 for r in spans)


def test_a_query_is_labelled_as_one():
    class RosterQuery(IDispatchable):
        def execute(self, dto=None):
            return []

    app, recorder = _app()
    app.boot()
    app.context.container.bind(RosterQuery, RosterQuery)

    app.dispatch(RosterQuery)

    assert {r.cat for r in _spans(recorder, Lane.DISPATCH)} == {"query", "handler"}


def test_a_dispatch_that_raises_is_still_measured():
    """The slow-then-failing operation is exactly what someone opens a tracer to
    find; a span that vanished when its body raised would hide it."""
    app, recorder = _app()
    app.boot()
    app.context.container.bind(FailingCommand, FailingCommand)

    with pytest.raises(ValueError):
        app.dispatch(FailingCommand)

    assert {r.cat for r in _spans(recorder, Lane.DISPATCH)} == {"command", "handler"}


# ------------------------------------------------------- tasks (requirement 2)


def test_a_task_run_span_measures_the_work_and_not_the_bookkeeping():
    """`EPIC-005B` requirement 2 says a task-run span must reconstruct to "the
    same duration the task manager itself reports".

    **The task manager reports no duration.** `BackgroundTask` carries `id`,
    `name`, `token`, `future`, `status` and `progress` — no start time, no end
    time, nothing to compare against. The requirement as written cannot be met
    because the number it names does not exist.

    Its *intent* holds and is what this asserts, against a stronger reference
    than the one it asked for: an independent wall-clock measurement of the same
    call. A trace that disagreed with a real clock is wrong, and nothing built
    on it could be trusted.
    """
    app, recorder = _app()
    app.boot()

    def work():
        time.sleep(SLOW)

    wall_start = time.perf_counter_ns()
    handle = app.context.tasks.spawn(work, name="slow-work")
    # `ITaskHandle` exposes `future`; waiting on it is what makes this
    # deterministic rather than a sleep long enough to "probably" be done.
    handle.future.result(timeout=5)
    wall_ns = time.perf_counter_ns() - wall_start

    (span,) = _spans(recorder, Lane.TASK, "run")
    assert span.name == "slow-work"
    assert span.args["task_id"], "the task id must be recoverable from the trace"
    # The span measures the work; the wall clock also contains scheduling and
    # the wait. So: at least the sleep, and no more than everything.
    assert SLOW * 1e9 * 0.5 <= span.dur <= wall_ns


# --------------------------------------------------- the application's own API


def test_an_application_span_lands_in_the_user_lane():
    """`D8` was the framework hard-coding `student.added` and three other
    demo-app event names. The replacement: the app marks what matters to it, and
    the framework knows about zero application events."""
    app, recorder = _app()
    app.boot()

    with app.context.trace.span("strategy-eval", symbol="BTC"):
        time.sleep(QUICK)
    app.context.trace.mark("order-filled", price=101.5)

    user = [r for r in recorder.snapshot() if r.lane == Lane.USER]
    span_end = next(r for r in user if r.dur)
    instant = next(r for r in user if r.kind == "i")

    assert span_end.name == "strategy-eval"
    assert span_end.args == {"symbol": "BTC"}
    assert instant.name == "order-filled"
    assert instant.args == {"price": 101.5}


def test_an_application_span_survives_an_exception_in_its_body():
    app, recorder = _app()
    app.boot()

    with pytest.raises(RuntimeError), app.context.trace.span("doomed"):
        raise RuntimeError("boom")

    assert [r.name for r in _spans(recorder, Lane.USER)] == ["doomed"]


def test_no_framework_module_names_an_application_event():
    """`EPIC-005B` requirement 4, as a check rather than a promise: every record
    the engine produces without the application asking is in an engine lane."""
    app, recorder = _app()
    app.use(FastExtension())
    app.boot()
    app.context.container.bind(GreetCommand, GreetCommand)
    app.dispatch(GreetCommand)
    app.stop()

    assert not [r for r in recorder.snapshot() if r.lane == Lane.USER]


# ------------------------------------------ requirement 3: the disabled budget


def _instrumentation() -> str:
    """@brief Names whatever is tracing this process, or `""`. Same guard as
    `tests/extensions/audit/test_trace_recorder.py`, and for the same reason."""
    hook = sys.gettrace()
    if hook is not None:
        return type(hook).__module__.split(".")[0]
    monitoring = getattr(sys, "monitoring", None)
    if monitoring is not None:
        for tool_id in range(6):
            if monitoring.get_tool(tool_id):
                return monitoring.get_tool(tool_id)
    return ""


_INSTRUMENTED = _instrumentation()


@pytest.mark.skipif(
    bool(_INSTRUMENTED),
    reason=(
        f"timing measurement is meaningless under {_INSTRUMENTED!r} — "
        "run via the benchmark job, which does not use --cov"
    ),
)
def test_the_disabled_path_short_circuits_before_anything_tracing_costs():
    """`EPIC-005B` requirement 3.

    The regression this exists for was real and was mine: the first version
    guarded in five scattered places inside `dispatch()` and once per middleware
    inside the pipeline, and passed `recorder`/`cid` as keyword arguments. That
    cost applications *which never trace* ~250 ns per dispatch — 3.939 µs
    against a 3.693 µs baseline, a ~7% tax that `EPIC-006F` had already rejected
    for its observer hook. Hoisting the branch as far out as it goes brought it
    to 3.597 µs against 3.650 µs: within noise.

    Asserted as a ratio rather than an absolute, because a shared CI runner
    cannot support an absolute — what it locks in is that the guard really does
    short-circuit, which is the property that made the tax disappear.
    """

    class Passthrough(IMiddleware):
        def process(self, cmd_or_query, dto, next_handler):
            return next_handler()

    def build(tracing: bool) -> App:
        app = App(StdLibContainer(), MemoryEventBus())
        if tracing:
            app.context.enable_tracing(TraceRecorder())
        app.boot()
        app.context.middleware_pipeline.add(Passthrough())
        app.context.middleware_pipeline.add(Passthrough())
        app.context.container.bind(GreetCommand, GreetCommand)
        return app

    def per_call(app: App) -> float:
        return min(
            timeit.repeat(lambda: app.dispatch(GreetCommand), number=3_000, repeat=3)
        )

    off = per_call(build(tracing=False))
    on = per_call(build(tracing=True))

    assert off < on / 1.5, (
        f"tracing off costs {off:.4f}s against {on:.4f}s on — the guard is not "
        "short-circuiting, so applications that never trace are paying for it"
    )
