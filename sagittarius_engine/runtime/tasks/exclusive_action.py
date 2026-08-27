import functools
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


@dataclass(frozen=True, slots=True)
class HeldSlot:
    """
    @brief Which key holds an `ExclusiveAction`'s one slot, and for how long —
    `EPIC-007B`.

    @details Singular by construction: one instance has exactly one slot (see the
    class docstring below), so at most one `HeldSlot` can ever describe it — this is
    `held_slot()`, not a plural `held_slots()`, because the class it reports on holds
    at most one key at a time.

    @param held_seconds On the monotonic clock, like every other duration this engine
        measures — wall-clock is the wrong clock for "how long", and is not what a
        slot held far longer than its task runs needs to answer.
    """

    key: str
    held_seconds: float


class ExclusiveAction:
    """
    @brief Single-flight coordination for one or more named background
    actions that must never run concurrently with each other.

    @details Closes engine defect class D (BOT-027 / BOT-069): a hand-rolled
    boolean flag plus an FSM check, duplicated at the top of every entry
    point that needs to reject a re-click while a previous run is still in
    flight, with the reset easy to forget in an exception path. One
    `ExclusiveAction` instance holds exactly one "currently running" slot —
    every key ever passed to the SAME instance is therefore mutually
    exclusive with every other key on that instance, which is how cross-key
    exclusion groups work here: don't invent a separate "group" concept,
    just share one instance between the actions that must exclude each
    other, and give each its own instance otherwise.

    Two-phase on purpose (`try_start()` then `submit()`, not one atomic
    call): real call sites in this codebase (`StreamLifecycleController`)
    do main-thread work — building chart cards, rebuilding indicator
    scripts — strictly BETWEEN "is a slot free" and "hand off to the
    background" (that ordering already avoids a real race on the indicator
    set, see stream_lifecycle_controller.py's own history). A single
    combined method would force that main-thread work to be either
    entirely before the reservation (races the guard) or inside the
    background task itself (races the fact it must run on the main thread
    at all).

    Pure Python, no Qt dependency — same convention as `ResourceScope` and
    `CancellationToken` in this package.

    Usage:
        self._stream_actions = ExclusiveAction(thread_manager=self._thread_manager)
        ...
        if not self._stream_actions.try_start("load_history"):
            self._view_model.log_model.append("Wait for the current run to finish.")
            return
        self._ensure_chart_cards(symbols)   # main thread, after the guard
        self._rebuild_scripts()             # main thread, before submit
        self._stream_actions.submit("load_history", self._run_load_history, symbols, ...)
    """

    def __init__(self, thread_manager: "IThreadManager") -> None:
        self._thread_manager = thread_manager
        self._lock = threading.Lock()
        self._running_key: str | None = None
        # EPIC-007B: monotonic, set the instant the slot is reserved, read by
        # held_slot() — a slot held far longer than its task runs is a leaked
        # single-flight key, and the control it guards never re-enables.
        self._started_at: float | None = None

    def try_start(self, key: str) -> bool:
        """
        @brief Atomically reserves the single slot for `key` if nothing is
        currently running on this instance (neither `key` itself re-entering,
        nor any other key sharing this instance).
        @returns True if reserved — caller now owns the slot and must
        eventually release it, normally by calling `submit()` (which
        releases automatically), or `finish()` directly if it bails out
        before submitting anything. False if something is already running.
        """
        with self._lock:
            if self._running_key is not None:
                return False
            self._running_key = key
            self._started_at = time.monotonic()
            return True

    def submit(
        self, key: str, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Future:
        """
        @brief Submits `task(*args, **kwargs)` to the thread manager exactly
        as `IThreadManager.submit()` itself would — `task` is not wrapped —
        and releases the `key` reservation once the resulting `Future`
        settles, success or exception, via `add_done_callback()`. That's the
        release step every hand-rolled version of this pattern has had to
        remember on its own. Assumes `key` was already reserved via
        `try_start()`.
        @details Not wrapping `task` (a done-callback instead of a try/finally
        around the call) keeps `thread_manager.submit`'s own call args exactly
        what a caller passed in — needed for `IThreadManager` test doubles
        that assert on `submit.call_args` expecting `task` as the first
        positional argument, not an opaque partial. `Future.add_done_callback`
        fires for a future that already finished by the time it's attached
        (calls back immediately, same thread) as well as one that finishes
        later — no gap where a fast task's release could be missed.
        """
        future = self._thread_manager.submit(task, *args, **kwargs)
        future.add_done_callback(functools.partial(self._release_on_done, key))
        return future

    def _release_on_done(self, key: str, future: Future) -> None:
        self.finish(key)

    def finish(self, key: str) -> None:
        """@brief Releases the slot if `key` currently holds it — a no-op
        otherwise (e.g. called twice, or for a key that never held it)."""
        with self._lock:
            if self._running_key == key:
                self._running_key = None
                self._started_at = None

    def held_slot(self) -> HeldSlot | None:
        """@brief The key holding this instance's one slot, and how long it
        has held it — `None` if the slot is free. `EPIC-007B`."""
        with self._lock:
            if self._running_key is None or self._started_at is None:
                return None
            return HeldSlot(
                key=self._running_key,
                held_seconds=time.monotonic() - self._started_at,
            )

    def is_running(self, key: str | None = None) -> bool:
        """@brief True if `key` is the one currently running, or — when
        `key` is omitted — True if ANY key on this instance is running."""
        with self._lock:
            if key is None:
                return self._running_key is not None
            return self._running_key == key
