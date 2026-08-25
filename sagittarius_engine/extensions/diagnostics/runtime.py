"""`RuntimeMonitor` — anomalies that are only visible while the app runs
(`EPIC-006F`).

Everything else in this package inspects **structure**: it holds still while
you look at it, and one pass at readiness sees all of it. These two checks
watch **behaviour**, which means they run for the life of the process — so the
first design constraint is not what they find, it is what they cost.

@par The two checks

| | |
| :--- | :--- |
| **R1** | An event was emitted and **nothing was listening** |
| **R2** | A handler **raised** |

@par R1 is not A1
`A1` is static and advisory: *this event is declared and nobody subscribes*,
which is true of most of the engine's own events in most applications and is
usually fine. R1 fires only when something actually **published into the
void** — a real emit, at runtime, that reached nobody. A1 asks "is anyone
listening?"; R1 says "you just spoke and nobody heard you". The second is a
defect far more often than the first.

@par What is deliberately not here
`EPIC-006F`'s draft also listed *a task running past an expected duration*.
That is cut, on the spec's own instruction to resolve the overlap with
`EPIC-005` rather than build both: "how long did this take" is the question a
trace recorder is shaped around, and a second implementation here would be the
worse one.

*A hosted service that died after starting* is deferred for a different and
measured reason: there is no signal for it. A service that fails to **start**
raises, and boot aborts loudly (`hosted_service_manager.py:53`); one that
starts and later dies emits nothing and is caught nowhere, so detecting it
needs new instrumentation in the runtime rather than observation of what
already exists. That is a change to the runtime's contract, not a diagnostic,
and it does not belong in the same commit as one.
"""

from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass, field

from sagittarius_engine.infrastructure.event_bus.bus_observers import (
    IBusObserver,
    add_bus_observer,
    remove_bus_observer,
)

from .report import Finding, WiringReport

#: Frames inside these packages are the bus getting to the emit, not the code
#: that chose to emit — skipped when naming the site an unheard event came from.
_ENGINE_DISPATCH_PREFIXES = (
    "sagittarius_engine/infrastructure/event_bus",
    "sagittarius_engine\\infrastructure\\event_bus",
    "sagittarius_engine/kernel",
    "sagittarius_engine\\kernel",
    # This package's own frames. Omitting them made every R1 finding report
    # `runtime.py` as the emit site -- the monitor pointing at itself, which
    # is both useless and quietly wrong. Caught by running it, not by reading
    # it: the code looked right, and `reversed()` starts at the innermost
    # frame, which is this observer.
    "sagittarius_engine/extensions/diagnostics",
    "sagittarius_engine\\extensions\\diagnostics",
)


@dataclass
class _UnheardEvent:
    """@brief What is remembered about one event name nobody listened to."""

    count: int = 0
    #: Captured on the **first** occurrence only. See `RuntimeMonitor` for why.
    first_site: str = ""


@dataclass
class _FailedHandler:
    """@brief What is remembered about one (event, handler) pair that raised."""

    count: int = 0
    first_exception: str = ""
    exception_types: set[str] = field(default_factory=set)


class RuntimeMonitor(IBusObserver):
    """
    @brief Watches the bus and remembers what looked wrong.

    @details Registered with `add_bus_observer()`, so it sees every emit and
    every handler failure in the process, through whichever bus — the two
    funnels it observes are shared by all of them.

    @par Cost, which is the whole design
    A diagnostic that perturbs what it measures is worse than none, so this
    class does the least it can on the hot path:

    - **Aggregates, never accumulates.** One dict entry per *distinct* event
      name or (event, handler) pair, not one record per occurrence. An
      application emitting an unheard event in a loop costs one integer
      increment per emit, and the memory is bounded by how many distinct names
      exist — which is bounded by the program.
    - **Captures a stack once.** Naming the emit site is what makes R1
      actionable, and `traceback.extract_stack()` is far too expensive to run
      per emit. It runs on the **first** occurrence of each name only. The
      honest cost of that: the site reported is where it *first* happened, and
      a second emit site for the same name is invisible. Reporting the name
      with one real site beats reporting no site, and beats paying for a stack
      walk on every dispatch.
    - **Holds one lock, briefly.** Emits arrive on whichever thread published,
      including pool threads.

    @par Usage
    Normally through `DiagnosticsExtension(watch_runtime=True)`, which
    registers and unregisters it around the application's life. Directly:

    @code
    monitor = RuntimeMonitor()
    monitor.start()
    ...
    print(monitor.report().format())
    monitor.stop()
    @endcode

    @param expected_unheard Event names this application knowingly emits with
        nobody listening. Same argument, same meaning as check A1's.
    @param include_engine_events Report R1 for events the **engine itself**
        declares (`app.ready`, `extension.started`, `runtime.scheduler.*`, ...)
        as well as the application's own. Off by default, and that default was
        measured: a trivial application booting and stopping produced six R1
        warnings, five of which were the engine's own lifecycle events that no
        application has any reason to handle. That is the flood `A1` is
        advisory to avoid — a warning stream that is mostly noise teaches the
        reader to skip the report, which costs more than the check finds.

        The distinction is exact rather than a guess at the name: every
        registration records its declaring module, so "the engine declared
        this" is `EventEntry.module.startswith("sagittarius_engine.")`.
    """

    def __init__(
        self,
        *,
        expected_unheard: tuple[str, ...] = (),
        include_engine_events: bool = False,
    ) -> None:
        self.expected_unheard = frozenset(expected_unheard)
        self.include_engine_events = include_engine_events
        self._unheard: dict[str, _UnheardEvent] = {}
        self._failures: dict[tuple[str, str], _FailedHandler] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------- lifecycle

    def start(self) -> None:
        """@brief Begins observing. Idempotent, via `add_bus_observer()`."""
        add_bus_observer(self)

    def stop(self) -> None:
        """@brief Stops observing. What was already seen is kept, so a report
        can still be read after shutdown — which is when it is usually read."""
        remove_bus_observer(self)

    def reset(self) -> None:
        """@brief Forgets everything seen so far, without unregistering."""
        with self._lock:
            self._unheard.clear()
            self._failures.clear()

    # -------------------------------------------------------- observer hooks

    def event_emitted(self, event_name: str, handler_count: int) -> None:
        """@brief R1. Returns immediately for the overwhelmingly common case of
        an event that had listeners — one integer comparison."""
        if handler_count:
            return
        if event_name in self.expected_unheard:
            return

        with self._lock:
            entry = self._unheard.get(event_name)
            if entry is None:
                # First time for this name: pay for the stack walk exactly once.
                entry = _UnheardEvent(first_site=_calling_site())
                self._unheard[event_name] = entry
            entry.count += 1

    def handler_failed(self, event_name: str, handler: str, exc: BaseException) -> None:
        """@brief R2."""
        key = (event_name, handler)
        with self._lock:
            entry = self._failures.get(key)
            if entry is None:
                entry = _FailedHandler(first_exception=f"{type(exc).__name__}: {exc}")
                self._failures[key] = entry
            entry.count += 1
            entry.exception_types.add(type(exc).__name__)

    # --------------------------------------------------------------- reading

    @property
    def is_clean(self) -> bool:
        """@brief True when nothing anomalous has been seen."""
        with self._lock:
            return not self._unheard and not self._failures

    def report(self) -> WiringReport:
        """
        @brief What has been seen, in the same vocabulary as the static checks.

        @details Deliberately a `WiringReport` rather than a new type: an
        operator reading a build should not have to learn two report formats
        because one set of checks happened to run at a different time.
        """
        return WiringReport(findings=tuple(self.findings()))

    def findings(self) -> list[Finding]:
        """@brief The anomalies, sorted so two identical runs read identically."""
        with self._lock:
            unheard = sorted(self._unheard.items())
            failures = sorted(self._failures.items())

        # Filtered here rather than in `event_emitted()`, for two reasons. The
        # registry is populated as modules import, so at construction time it
        # is not yet complete and the answer would be wrong; and the hot path
        # stays free of a registry lookup per emit. The cost is that everything
        # is counted either way — which is what lets `include_engine_events`
        # reveal them without re-running the application.
        if not self.include_engine_events:
            engine_declared = _engine_declared_events()
            unheard = [(n, e) for n, e in unheard if n not in engine_declared]

        found: list[Finding] = [
            Finding(
                check="R1",
                # A warning, not an error. Emitting into the void is very often
                # a real defect -- and is also exactly what a feature behind a
                # flag, or an event whose only subscriber is optional, looks
                # like. Failing a build on it would make the check the first
                # thing an operator switched off.
                severity="warning",
                subject=name,
                message=(
                    f"emitted {entry.count}x at runtime with no handler "
                    "subscribed — nothing received it"
                ),
                hint=(
                    f"first emitted from {entry.first_site}"
                    if entry.first_site
                    else "pass it in expected_unheard if this is intentional"
                ),
            )
            for name, entry in unheard
        ]

        found.extend(
            Finding(
                check="R2",
                # An error: a handler that raised did not do its work, and
                # the bus isolated the failure so nothing else noticed. That
                # isolation is correct (`handler_reporting.py`) and is exactly
                # why this needs surfacing somewhere other than a log line.
                severity="error",
                subject=f"{handler} on '{event_name}'",
                message=(
                    f"raised {entry.count}x while handling this event "
                    f"({', '.join(sorted(entry.exception_types))})"
                ),
                hint=f"first failure: {entry.first_exception}",
            )
            for (event_name, handler), entry in failures
        )

        return found


def _engine_declared_events() -> frozenset[str]:
    """
    @brief Event names declared by the engine itself, rather than by the
    application under observation.

    @details Read from `EventRegistry`, which records the declaring module of
    every registration — so this is exact, not a guess from the name. An
    application is free to declare an event called `app.anything`; it will not
    be filtered, because its module is not the engine's.
    """
    from sagittarius_engine.domain.event_registry import EventRegistry

    return frozenset(
        entry.event_name
        for entry in EventRegistry.all()
        if entry.module.startswith("sagittarius_engine.")
    )


def _calling_site() -> str:
    """
    @brief `file.py:line` of the first frame outside the engine's dispatch code.

    @details Walked from the top of the stack downwards, skipping the bus and
    kernel frames that got us here — those are always the same and never what
    the reader needs. Returns `""` rather than guessing if every frame is
    engine code, which happens when the engine emits its own lifecycle events.
    """
    for frame in reversed(traceback.extract_stack()[:-1]):
        if not any(prefix in frame.filename for prefix in _ENGINE_DISPATCH_PREFIXES):
            return f"{frame.filename}:{frame.lineno}"
    return ""
