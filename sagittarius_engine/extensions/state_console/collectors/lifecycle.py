"""`LifecycleCollector` — `EPIC-007C`.

Reads the same four subsystems `WiringInspector.inspect_lifecycle()` already
reads, by the same attribute names — `registered_extensions`,
`initialized_extensions`, `ext.descriptor.name/enabled/dependencies`,
`services`, `started_services`, `jobs`, `job.next_run` — so this collector
and that inspector never drift about what those words mean.

@warning `scheduler_jobs_without_next_run` reads `context.scheduler.jobs`
live, the same as `WiringInspector`'s D3 check. Found while implementing
`EPIC-007D`'s demo seed for this exact condition: a real `Scheduler`'s
background thread drops a `next_run=None` job from `.jobs` on its very next
wake — `add_job()` itself calls `notify_all()`, so that "next wake" is
essentially immediate — which means this field can be non-zero for a real
`Scheduler` only in the narrow instant between a job going dead and that
thread's next loop iteration. It is honest (never wrong), but is not a
reliable way to observe this condition against this engine's own
`Scheduler`. See `examples/student_management/infrastructure/demo_faults/`
for how the demo seed works around it. `jobs` (`EPIC-008E`) reads the exact
same live list and inherits the identical fragility: a broken job's own row
in the Limits jobs table can vanish between one snapshot and the next for
the same reason the aggregate count can.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sagittarius_engine.extensions.audit.contracts import (
    JobRecord,
    LifecycleState,
    ModuleState,
)
from sagittarius_engine.extensions.state_console.collector import ISnapshotSection
from sagittarius_engine.kernel.lifecycle import EngineLifecycle


class LifecycleCollector(ISnapshotSection[LifecycleState]):
    """
    @brief Where the engine got to, and how many of what it manages are up.

    @details Constructor-injected, narrowly, per `WiringInspector`'s own
    precedent — a two-line fixture can test this without booting an
    application.

    @warning `transitions` is always `()`. Nothing in `EngineLifecycle`
    records a history of state changes with timestamps today — it holds only
    the *current* `state`. Named here rather than fabricated: adding real
    transition tracking is its own small change to `kernel/lifecycle.py`,
    out of scope for a collector that only reads what already exists.
    """

    def __init__(
        self,
        lifecycle: EngineLifecycle,
        *,
        extension_manager: Any = None,
        hosted_services: Any = None,
        scheduler: Any = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._extension_manager = extension_manager
        self._hosted_services = hosted_services
        self._scheduler = scheduler

    def collect(self) -> LifecycleState:
        extensions_registered = 0
        extensions_initialized = 0
        modules: tuple[ModuleState, ...] = ()
        if self._extension_manager is not None:
            registered = self._extension_manager.registered_extensions
            extensions_registered = len(registered)
            extensions_initialized = len(self._extension_manager.initialized_extensions)
            # By name, not object identity -- the same set WiringInspector's
            # own D1 check builds (inspector.py::_extensions), so "ready"
            # here can never disagree with what sagittarius-doctor reports.
            initialized_names = {
                ext.descriptor.name
                for ext in self._extension_manager.initialized_extensions
            }
            modules = tuple(
                ModuleState(
                    name=ext.descriptor.name,
                    ready=ext.descriptor.name in initialized_names,
                )
                for ext in registered
            )

        hosted_registered = 0
        hosted_started = 0
        if self._hosted_services is not None:
            hosted_registered = len(self._hosted_services.services)
            hosted_started = len(self._hosted_services.started_services)

        scheduler_jobs = 0
        scheduler_jobs_without_next_run = 0
        job_records: tuple[JobRecord, ...] = ()
        if self._scheduler is not None:
            scheduler_job_list = self._scheduler.jobs
            scheduler_jobs = len(scheduler_job_list)
            scheduler_jobs_without_next_run = sum(
                1
                for job in scheduler_job_list
                if getattr(job, "next_run", None) is None
            )
            now = datetime.now()
            job_records = tuple(
                JobRecord(
                    name=getattr(job.fn, "__name__", "job"),
                    trigger=job.trigger.describe(),
                    next_fire_seconds=(job.next_run - now).total_seconds()
                    if job.next_run is not None
                    else None,
                )
                for job in scheduler_job_list
            )

        return LifecycleState(
            state=self._lifecycle.state.value,
            transitions=(),
            extensions_registered=extensions_registered,
            extensions_initialized=extensions_initialized,
            hosted_registered=hosted_registered,
            hosted_started=hosted_started,
            scheduler_jobs=scheduler_jobs,
            scheduler_jobs_without_next_run=scheduler_jobs_without_next_run,
            modules=modules,
            jobs=job_records,
        )
