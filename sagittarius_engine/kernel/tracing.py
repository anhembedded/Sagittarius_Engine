"""`ctx.trace` — how an **application** instruments itself (`EPIC-005B`).

@par This is what properly retires `D8`
`D8` was the framework hard-coding `student.added` and three other demo-app
event names inside `AuditService`: the engine knowing about one application's
domain. The replacement is the opposite arrangement — the application marks
what matters to it, and the framework knows about **zero** application events.
That is SystemView's user-marker model.

@code
ctx.trace.mark("order-filled", price=101.5)
with ctx.trace.span("strategy-eval", symbol="BTC"):
    evaluate()
@endcode

@par Two mechanisms, deliberately
The engine's own instrumentation does **not** go through this class. Kernel
sites read `context.recorder` and guard on `is not None`, because they run on
every dispatch and `EPIC-005A` measured that guard at ~3 ns over an empty call
site while a call through an object costs ~27 ns.

Application sites go through `ctx.trace`, which is **always present** even when
tracing is off. An API that made every application write
`if ctx.trace is not None:` around its own markers would be paying for the
engine's constraint at the place where it does not apply: a marker sits where
the application chose to put it, not in a loop the engine runs a million times.
The cost of that convenience is one attribute lookup and one `is None` check —
measured, and stated here rather than left to be discovered.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from sagittarius_engine.interfaces.i_trace_recorder import ITraceRecorder, Lane

if TYPE_CHECKING:  # pragma: no cover - import cycle at runtime
    from sagittarius_engine.kernel.context import EngineContext


class TraceApi:
    """
    @brief The application's handle on tracing. Safe to call when disabled.

    @details Reads the recorder off the context on every call rather than
    caching it, so `enable_tracing()` after this object was built still takes
    effect — otherwise an application that enabled tracing later would hold a
    handle that silently records nothing, which is the class of bug this whole
    epic is about.
    """

    __slots__ = ("_context",)

    def __init__(self, context: EngineContext) -> None:
        self._context = context

    @property
    def enabled(self) -> bool:
        """@brief Whether anything is being recorded. For an application that
        wants to skip building an expensive `args` payload."""
        return self._context.recorder is not None

    @property
    def recorder(self) -> ITraceRecorder | None:
        """@brief The recorder, or `None`. Exposed so a test or an exporter can
        read what was captured without reaching into the context."""
        return self._context.recorder

    def mark(self, name: str, **args: Any) -> None:
        """
        @brief Records an instant — something happened, at this moment.

        @param args Free-form, and only built into a dict when tracing is on:
            the `**args` collection itself is unavoidable, but nothing is
            serialised or copied further while disabled.
        """
        recorder = self._context.recorder
        if recorder is not None:
            recorder.instant(Lane.USER, name, args=args or None)

    @contextmanager
    def span(self, name: str, **args: Any) -> Iterator[None]:
        """
        @brief Records a span around a block — something took this long.

        @details The span is closed in a `finally`, so a block that raises is
        still measured and still appears in the trace. A span that silently
        vanished when its body failed would hide exactly the slow-then-failing
        operation someone opened a tracer to find.

        @code
        with ctx.trace.span("strategy-eval", symbol="BTC"):
            evaluate()
        @endcode
        """
        recorder = self._context.recorder
        if recorder is None:
            yield
            return

        payload = args or None
        started = recorder.span_begin(Lane.USER, name, args=payload)
        try:
            yield
        finally:
            recorder.span_end(Lane.USER, name, started, args=payload)
