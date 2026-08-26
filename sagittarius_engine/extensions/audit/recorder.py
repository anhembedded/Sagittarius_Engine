"""The ring-buffer trace recorder (`EPIC-005A`, requirement 3).

@par The whole design, in two lines
@code
hot path:   record → append a tuple to deque(maxlen=N) → return    O(1), no I/O, no lock
consumer:   drain in batches → build TraceRecords → encode → send  somewhere else entirely
@endcode

A bounded `collections.deque` gives an atomic append under the GIL and evicts
oldest-first. No allocation growth, no lock on the hot path, no unbounded list
that has to be re-collected — which is `EPIC-005`'s defect `D9`.

@par Retained by default
The recorder records whether or not anyone is watching, so **a consumer that
attaches after the interesting thing happened still sees it**. That is the
single most valuable property in the design and the one thing `py-spy` and
`viztracer` cannot offer either: attach to those after the fact and you see
"now", not "then".

@par Nothing is formatted at capture
No `strftime`, no f-strings, no `str()` of a payload. A tuple of primitives goes
in; `TraceRecord.from_row()` builds the typed object later, off the hot path.
Formatting at capture is what made the old `AuditService` cost more per event
than the work it observed.

@par Disabled means `None`, not a null object
Measured before this file was written, and the opposite of what `EPIC-005` §4.2
originally specified — see that section's correction. Against a 21.5 ns floor:
a call on a no-op object costs 48.8 ns, a `is not None` guard costs 24.5 ns.
So an instrumentation site is written:

@code
if self._trace is not None:
    self._trace.instant(Lane.TASK, "task.run", cid=task_id)
@endcode

and `_trace` is `None` when tracing is off. A branch is a load and a compare; a
call on a null object is a whole frame.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from sagittarius_engine.interfaces.i_trace_recorder import ITraceRecorder, Lane

from .contracts import Hello, RecordKind, TraceRecord

#: Retained-mode default. 100k 8-tuples is a few tens of MB at worst and covers
#: minutes of a busy application — long enough that "attach when it goes wrong"
#: still catches what went wrong.
DEFAULT_CAPACITY = 100_000


class TraceRecorder(ITraceRecorder):
    """
    @brief Captures records into a bounded ring buffer.

    @details Not an `IExtension` and not aware of one: this is the mechanism,
    and `EPIC-005B` is what decides where in the engine it gets called from.
    Keeping the two apart is what lets the overhead be measured on its own,
    which is the acceptance criterion this milestone turns on.

    @param capacity Records retained. Oldest are evicted first, and every
        eviction is counted — a trace with silent holes in it is worse than a
        short one, because it looks complete.
    """

    __slots__ = (
        "_buffer",
        "_capacity",
        "_dropped",
        "_epoch_ns",
        "_epoch_wall_ns",
        "_lock",
        "_next_cid",
        "_tap_failures",
        "_taps",
    )

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        self._capacity = capacity
        self._buffer: deque[tuple[Any, ...]] = deque(maxlen=capacity)
        # Both clocks, once. Durations come from the monotonic one; the wall
        # anchor is what lets a recording be lined up against a log file.
        self._epoch_ns = time.perf_counter_ns()
        self._epoch_wall_ns = time.time_ns()
        self._dropped = 0
        self._next_cid = 0
        #: Guards `_next_cid` only. **Never taken on the capture path** —
        #: `deque.append` is already atomic under the GIL, and a lock there
        #: would put contention into the thing being measured.
        self._lock = threading.Lock()
        #: Live subscribers (`EPIC-005D`'s `TraceServer`), notified with the
        #: raw row tuple, not a `TraceRecord` — building the typed object is
        #: exactly the cost §4.2 keeps off this path. Copy-on-write, same
        #: pattern and reason as `infrastructure/event_bus/bus_observers.py`:
        #: reads happen on every capture, writes happen when a client
        #: (dis)connects.
        self._taps: tuple[Callable[[tuple[Any, ...]], None], ...] = ()
        #: Times a tap raised and was contained. See `_notify_taps()`.
        self._tap_failures = 0

    def add_tap(self, callback: Callable[[tuple[Any, ...]], None]) -> None:
        """
        @brief Subscribes to every row as it is captured, from now on.

        @details Register **before** calling `snapshot()` for a backlog, not
        after: the two together (tap first, then read the backlog) can very
        rarely double-deliver a row captured in the gap between them, but
        never miss one. The other order can miss one. For a diagnostic
        stream, a duplicate is a shrug; a silent gap is the defect this
        engine's diagnostics exist to stop shipping.
        """
        if callback not in self._taps:
            self._taps = (*self._taps, callback)

    def remove_tap(self, callback: Callable[[tuple[Any, ...]], None]) -> None:
        """
        @brief Unsubscribes. Silent if `callback` was never registered, so a
        disconnect handler does not have to track whether registration
        actually succeeded.

        @details Compares with `==`, matching `add_tap()`'s `in` check —
        deliberately **not** `is`. A bound method (`recorder.add_tap(self._on_row)`
        ... `recorder.remove_tap(self._on_row)`, the ordinary way to
        subscribe and unsubscribe) creates a new wrapper object on every
        attribute access: `self._on_row is self._on_row` is `False`, while
        `self._on_row == self._on_row` is `True`. An identity comparison here
        would make that completely normal pattern silently fail to
        unsubscribe — found by writing a test that used `seen.append` twice
        and watching `remove_tap` do nothing.
        """
        self._taps = tuple(t for t in self._taps if t != callback)

    def _notify_taps(self, row: tuple[Any, ...]) -> None:
        """@brief Fans a captured row out to live subscribers.

        @details Exceptions are contained, never propagated: a broken tap —
        a client that disconnected mid-send, a queue that is full — must not
        take down the application it is only supposed to be observing. The
        same rule, and the same reason, as `bus_observers.py`'s handling of a
        broken diagnostic observer.

        **Counted, not swallowed**, for the same reason `EPIC-006F` changed
        `bus_observers.py` to count (`b7783c3`): a `pass` here means a tap
        that fails on every single row looks identical to one that is working,
        and a diagnostic tool that hides its own failures is the defect this
        engine exists to stop shipping. `tap_failures` is what makes it
        visible. Logging instead would be worse — this runs on the capture
        path, and a broken tap would then produce one log line per record."""
        for tap in self._taps:
            try:
                tap(row)
            except Exception:  # noqa: BLE001 - contained and counted; see above
                self._tap_failures += 1

    # --------------------------------------------------------- the hot path

    def instant(
        self,
        lane: Lane,
        name: str,
        cat: str = "",
        cid: int = 0,
        args: dict[str, Any] | None = None,
    ) -> None:
        """
        @brief Records a point in time. ~157 ns measured, against a 2 µs budget.

        @details The eviction check reads `len(self._buffer)` rather than
        catching an overflow, because a `deque(maxlen=...)` discards silently —
        there is no signal to catch. Comparing against capacity is the only way
        to know a record was lost, and it costs one integer compare.
        """
        if len(self._buffer) == self._capacity:
            self._dropped += 1
        row = (
            time.perf_counter_ns() - self._epoch_ns,
            RecordKind.INSTANT.value,
            lane.value,
            name,
            cat,
            cid,
            0,
            args,
        )
        self._buffer.append(row)
        if self._taps:
            self._notify_taps(row)

    def span_begin(
        self,
        lane: Lane,
        name: str,
        cat: str = "",
        cid: int = 0,
        args: dict[str, Any] | None = None,
    ) -> int:
        """
        @brief Opens a span and returns the monotonic start, to be handed back
        to `span_end()`.

        @details The start is returned rather than stored in a table keyed by
        id: a table would need a lock, would grow without bound if a span were
        never closed, and would make a nested span on another thread ambiguous.
        Handing the caller an opaque integer makes the pairing the caller's
        problem, which is where it can actually be got right.
        """
        started = time.perf_counter_ns()
        if len(self._buffer) == self._capacity:
            self._dropped += 1
        row = (
            started - self._epoch_ns,
            RecordKind.SPAN.value,
            lane.value,
            name,
            cat,
            cid,
            0,
            args,
        )
        self._buffer.append(row)
        if self._taps:
            self._notify_taps(row)
        return started

    def span_end(
        self,
        lane: Lane,
        name: str,
        started: int,
        cat: str = "",
        cid: int = 0,
        args: dict[str, Any] | None = None,
    ) -> None:
        """@brief Closes a span opened by `span_begin()`, writing its duration.

        @param started Exactly what `span_begin()` returned."""
        now = time.perf_counter_ns()
        if len(self._buffer) == self._capacity:
            self._dropped += 1
        row = (
            now - self._epoch_ns,
            RecordKind.SPAN.value,
            lane.value,
            name,
            cat,
            cid,
            now - started,
            args,
        )
        self._buffer.append(row)
        if self._taps:
            self._notify_taps(row)

    def next_cid(self) -> int:
        """@brief A fresh correlation id. Locked, and deliberately **not** part
        of the capture path — a caller takes one when it starts a unit of work,
        not once per record."""
        with self._lock:
            self._next_cid += 1
            return self._next_cid

    # ------------------------------------------------------------- draining

    def drain(self, limit: int | None = None) -> tuple[TraceRecord, ...]:
        """
        @brief Removes and returns up to `limit` records, oldest first.

        @details Typed objects are built **here**, not at capture: this runs on
        the publisher's thread, where the cost is the consumer's, not the
        observed application's.

        Uses `popleft()` in a loop rather than copying and clearing, so that
        records arriving mid-drain are not lost — with a copy-then-clear, an
        append landing between the two would be discarded, and a trace that
        silently loses records under load is worse than one that admits it.
        """
        count = len(self._buffer) if limit is None else min(limit, len(self._buffer))
        rows: list[tuple[Any, ...]] = []
        for _ in range(count):
            try:
                rows.append(self._buffer.popleft())
            except IndexError:  # pragma: no cover - another drainer won the race
                break
        return tuple(TraceRecord.from_row(row) for row in rows)

    def snapshot(self) -> tuple[TraceRecord, ...]:
        """@brief Everything retained, **without** consuming it — the
        retained-mode read for a consumer that attached late. `list()` of a
        deque is atomic under the GIL, so this does not need the lock."""
        return tuple(TraceRecord.from_row(row) for row in list(self._buffer))

    # ------------------------------------------------------------ reporting

    @property
    def dropped(self) -> int:
        """@brief Records evicted because the buffer was full. A consumer that
        does not show this is presenting a trace with holes as complete."""
        return self._dropped

    @property
    def tap_failures(self) -> int:
        """@brief Times a live tap raised and was contained by `_notify_taps()`.

        @details Non-zero means a consumer is missing records it will never be
        told about — the connection is up, the stream just has holes in it."""
        return self._tap_failures

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        return len(self._buffer)

    def hello(self) -> Hello:
        """@brief The handshake describing this session, for a connecting
        consumer.

        @details `clock_resolution_ns=1000` is honest rather than aspirational:
        `perf_counter_ns()` reports nanoseconds, but an instrumentation call in
        CPython costs ~157 ns and the clock read alone is ~54 ns, so
        sub-microsecond differences are not meaningful and a consumer must not
        draw them as if they were."""
        return Hello(
            epoch_wall_ns=self._epoch_wall_ns,
            clock_resolution_ns=1000,
            capacity=self._capacity,
            dropped_before_connect=self._dropped,
        )

    def clear(self) -> None:
        """@brief Empties the buffer and the drop count. For tests and for an
        operator starting a fresh recording."""
        self._buffer.clear()
        self._dropped = 0
