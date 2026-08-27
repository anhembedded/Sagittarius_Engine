"""`DemoFaultsExtension` — `EPIC-007D` §2.2: one instance of each condition
the engine's diagnostics claim to detect, planted on demand.

@par Why this is its own extension, not a `-DemoFaults` branch inside `main.py`
Every fault here is exactly what `sagittarius-doctor --strict` exists to
catch (`EPIC-007D` §3). `doctor_target.build()` calls `build_app()` with no
`extra_extensions`, so an extension reaches the app only through that
parameter — keeping every fault behind this one, separately-opted-into
class is what keeps the doctor gate green. See
`Tasks/refix/completed/REF-005_...md` for a correction made while writing
this: `EnrolmentFlow`'s illegal move raises, it does not return `False`.

@par What is deliberately NOT wired here
`RuntimeMonitor` (R1/R2) and `ResilientEventBus`'s dead-letter queue are
observed directly by this extension and logged at shutdown, matching
`DiagnosticsExtension(watch_runtime=True)`'s own pattern — but neither
reaches `sagittarius-trace snapshot` today. `StateSnapshot` has no field for
either yet; that is `EPIC-007F`'s panel, not this milestone's.
`ExclusiveAction.held_slot()` (`EPIC-007B`) is seeded and real, for the same
reason: nothing in `EPIC-007C`'s collectors reads it yet. All three are
directly verifiable in this extension's own tests without a live console
attached.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sagittarius_engine.domain.event_registry import EventRegistry
from sagittarius_engine.extensions.diagnostics.runtime import RuntimeMonitor
from sagittarius_engine.infrastructure.event_bus.resilient_event_bus import (
    ResilientEventBus,
)
from sagittarius_engine.infrastructure.thread_manager import ThreadManager
from sagittarius_engine.interfaces import IExtension
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.exclusive_action import ExclusiveAction

from .enrolment_flow import EnrolmentFlow, drive_one_illegal_move

_MODULE = __name__

# A2: registered correctly, subscribed with a one-letter-dropped typo. Chosen
# so difflib's 0.8 cutoff finds the near match -- verified directly in this
# module's own test, not assumed.
_DECLARED_EVENT_NAME = "demo.roster_synced"
_TYPO_EVENT_NAME = "demo.roster_syncd"

# R1: emitted, subscribed to by nobody.
_UNHEARD_EVENT_NAME = "demo.roster_exported"

# R2 / dead letter: emitted through a ResilientEventBus wrapping the app's
# real bus, at a handler that always raises.
_FAILING_EVENT_NAME = "demo.student_deleted"

# D3: an interval a real job would plausibly use -- the value never matters,
# since this job is never scheduled (see _seed_dead_scheduled_job()).
_ONE_DAY = timedelta(hours=24)


class _ReportSystemClock:
    """@brief A plain, concrete, deliberately unregistered dependency -- C2's
    seed. Nothing about this class matters except that it is not an ABC and
    is never bound."""


class _ReportService:
    """@brief Needs `_ReportSystemClock`, which is never bound -- registered
    transient so `WiringInspector.inspect_container()` actually inspects it
    (a singleton reports `concrete=None` until resolved, and is skipped)."""

    def __init__(self, clock: _ReportSystemClock) -> None:
        self.clock = clock


class DemoFaultsExtension(IExtension[Any]):
    """
    @brief Plants one instance of every `EPIC-007D` §2.2 seed at readiness.

    @details Never registered by `doctor_target.build()` — see this module's
    docstring. Every seed is independently verifiable through this
    extension's own public attributes (`self.resilient_bus`,
    `self.runtime_monitor`, `self.exclusive_action`, `self.enrolment_flow`,
    `self.rejected_transition`) without a live `sagittarius-trace` client.
    """

    def __init__(self) -> None:
        self.dependencies: list[str] = []
        self.runtime_monitor = RuntimeMonitor()
        self.resilient_bus: ResilientEventBus | None = None
        self.exclusive_action: ExclusiveAction | None = None
        self.enrolment_flow: EnrolmentFlow | None = None
        self.rejected_transition: Exception | None = None
        self.dead_scheduled_job: Any = None

    def register(self, context: Any) -> None:
        pass

    def boot(self, context: Any) -> None:
        # Started in boot(), not at readiness, matching
        # DiagnosticsExtension(watch_runtime=True) -- R1/R2 during the rest of
        # boot are exactly as real as ones seen afterwards.
        self.runtime_monitor.start()
        context.lifecycle.when_ready(lambda: self._seed(context))

    def shutdown(self, context: Any) -> None:
        self.runtime_monitor.stop()
        report = self.runtime_monitor.report()
        logger = getattr(context, "logger", None)
        if logger is not None and (report.errors or report.warnings):
            logger.warning(f"DemoFaultsExtension runtime findings:\n{report.format()}")

    # ------------------------------------------------------------- seeding

    def _seed(self, context: Any) -> None:
        self._seed_typo_subscription(context)
        self._seed_unheard_emit(context)
        self._seed_dead_letter(context)
        self._seed_unbound_dependency(context)
        self._seed_dead_scheduled_job()
        self._seed_held_exclusive_slot(context)
        self._seed_illegal_fsm_transition()

    def _seed_typo_subscription(self, context: Any) -> None:
        """@brief A2 — declared correctly, subscribed with a typo."""
        EventRegistry.register_named(_DECLARED_EVENT_NAME, module=_MODULE)
        context.event_bus.on(_TYPO_EVENT_NAME, lambda _payload: None)

    def _seed_unheard_emit(self, context: Any) -> None:
        """@brief R1 — emitted at runtime, nobody subscribed."""
        context.event_bus.emit(_UNHEARD_EVENT_NAME, {"path": "/tmp/demo-roster.csv"})

    def _seed_dead_letter(self, context: Any) -> None:
        """@brief R2, and a dead letter once retries are spent. Wraps the
        app's real bus rather than replacing it -- `ResilientEventBus.on()`
        registers its retry wrapper on `inner_bus` directly, so the
        subscription lands on the same bus `EventCollector` already reads."""
        self.resilient_bus = ResilientEventBus(context.event_bus, max_retries=1)

        def _always_raises(_payload: Any) -> None:
            raise KeyError("demo: enrolment record missing")

        self.resilient_bus.on(_FAILING_EVENT_NAME, _always_raises)
        self.resilient_bus.emit(_FAILING_EVENT_NAME, {"student_id": "demo-0000"})

    def _seed_unbound_dependency(self, context: Any) -> None:
        """@brief C2 — a transient registration whose constructor needs a
        plain, unbound class. `_ReportSystemClock` is deliberately never
        registered."""
        context.container.bind(_ReportService, _ReportService)

    def _seed_dead_scheduled_job(self) -> None:
        """
        @brief D3 — a job seeded dead, and kept off the live `Scheduler`.

        @details Two findings from building this seed, not one:
        `context.scheduler` never organically leaves a job with
        `next_run=None` in `.jobs` (an exhausted job is dropped entirely),
        and setting it directly on a job actually appended to the live
        scheduler used to **crash its background thread outright**
        (`None <= datetime`, fixed in `runtime/scheduler/scheduler.py::_run()`
        — see that fix's own comment). With the crash fixed, appending a dead
        job to the live scheduler is merely *useless* rather than fatal:
        `add_job()` calls `notify_all()`, so the background thread's very
        next wake — essentially immediate — drops it again before anything
        has a chance to observe it there.

        So this seed never touches `context.scheduler` at all.
        `self.dead_scheduled_job` is a real, standalone `ScheduledJob`,
        stable for the life of this extension — the object a test or an
        operator points a `WiringInspector` at directly
        (`WiringInspector().inspect(scheduler=SimpleNamespace(jobs=[demo.dead_scheduled_job]))`),
        rather than a state briefly true of the running application's own
        scheduler.
        """
        from sagittarius_engine.runtime.scheduler.scheduler import ScheduledJob
        from sagittarius_engine.runtime.scheduler.triggers import IntervalTrigger

        def nightly_report() -> None: ...

        self.dead_scheduled_job = ScheduledJob(
            nightly_report, IntervalTrigger(_ONE_DAY)
        )
        self.dead_scheduled_job.next_run = None

    def _seed_held_exclusive_slot(self, context: Any) -> None:
        """@brief A slot taken and never released -- a visibly absurd age is
        just this process staying up."""
        try:
            thread_manager: IThreadManager = context.container.resolve(IThreadManager)
        except Exception:
            thread_manager = ThreadManager(max_workers=1, name="demo-faults")
        self.exclusive_action = ExclusiveAction(thread_manager=thread_manager)
        self.exclusive_action.try_start("demo-held-forever")
        # No finish()/submit() call: the slot stays held for the life of the
        # process, exactly like a real caller that forgot to release it.

    def _seed_illegal_fsm_transition(self) -> None:
        """@brief `EnrolmentFlow`, driven legally then once illegally.
        `transition_to()` raises rather than returning `False`
        (`REF-005`) -- caught here, the same way any real caller would have
        to."""
        self.enrolment_flow = EnrolmentFlow()
        self.rejected_transition = drive_one_illegal_move(self.enrolment_flow)
        logging.getLogger("App").info(
            "DemoFaultsExtension: rejected transition %s", self.rejected_transition
        )
