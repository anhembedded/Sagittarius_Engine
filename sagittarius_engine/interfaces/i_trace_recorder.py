"""What the engine calls to record a trace, and the vocabulary it needs
(`EPIC-005B`).

@par Why this is in `interfaces/` and not with the recorder
`tests/test_architecture.py` forbids `kernel/` from importing `extensions/`,
and the kernel is where most of the instrumentation lives — the extension
manager, the dispatcher, the middleware pipeline. The concrete recorder is
`extensions/audit/recorder.py`; the kernel depends on this abstraction and is
handed an implementation, which is the same shape as `IEventBus`/`IContainer`
and the reason those live here too.

`Lane` comes with it because an instrumentation site has to name one, so the
kernel needs the vocabulary as well as the verb. It is defined **once**, here,
and `extensions/audit/contracts.py` re-exports it — that module's whole
argument is that `D3`/`D4` happened because two schemas drifted, and a second
definition of `Lane` would be exactly that mistake.

@par Disabled is `None`, not an implementation of this
Measured in `EPIC-005A`: against a 21.5 ns floor, a call on a no-op object
costs 48.8 ns and an `is not None` guard costs 24.5 ns. So the no-op defaults
below are for **subclass ergonomics** — a partial implementation should not
have to write four empty methods — and never for the disabled path. An
instrumentation site reads:

@code
if self.context.recorder is not None:
    self.context.recorder.instant(Lane.KERNEL, "app.boot")
@endcode
"""

from __future__ import annotations

from abc import ABC
from enum import StrEnum
from typing import Any


class Lane(StrEnum):
    """
    @brief Which subsystem a record came from.

    @details A closed set, not a free string: the lane table goes over the wire
    in the `hello` message so a consumer can build its rows before the first
    batch arrives, and an unknown lane appearing mid-stream would mean
    rebuilding the view.

    Applications do not add lanes — their records go in `USER`. That is
    SystemView's user-marker model, and it is what lets the framework know
    about **zero** application events: `D8` was the engine hard-coding
    `student.added` and three other demo-app event names inside `AuditService`.
    """

    KERNEL = "kernel"
    EXTENSION = "extension"
    EVENT_BUS = "event_bus"
    DISPATCH = "dispatch"
    MIDDLEWARE = "middleware"
    TASK = "task"
    SCHEDULER = "scheduler"
    HOSTED = "hosted"
    USER = "user"


class ITraceRecorder(ABC):
    """
    @brief Captures trace records. The engine's side of the tracing contract.

    @details Every method is a **concrete no-op**, per `code-rule.md` §L, which
    forbids raising `NotImplementedError` from an inherited method. Same idiom
    as `IEventBus.subscriptions()`.

    @warning Implementations run **on the hot path**, on whichever thread is
    working. `EPIC-005` §4.2 budgets 2 µs per record; the shipped
    implementation measures ~157 ns. Anything that formats, allocates
    repeatedly, or takes a lock here is a defect.
    """

    def instant(
        self,
        lane: Lane,
        name: str,
        cat: str = "",
        cid: int = 0,
        args: dict[str, Any] | None = None,
    ) -> None:
        """@brief Records a point in time."""

    def span_begin(
        self,
        lane: Lane,
        name: str,
        cat: str = "",
        cid: int = 0,
        args: dict[str, Any] | None = None,
    ) -> int:
        """
        @brief Opens a span; returns the monotonic start to hand back to
        `span_end()`.

        @details Returning the start rather than storing it in a table keyed by
        id is deliberate: a table would need a lock, would grow without bound
        if a span were never closed, and would make a nested span on another
        thread ambiguous.
        """
        return 0

    def span_end(
        self,
        lane: Lane,
        name: str,
        started: int,
        cat: str = "",
        cid: int = 0,
        args: dict[str, Any] | None = None,
    ) -> None:
        """@brief Closes a span, writing its duration."""

    def next_cid(self) -> int:
        """@brief A fresh correlation id, for tying related records together."""
        return 0
