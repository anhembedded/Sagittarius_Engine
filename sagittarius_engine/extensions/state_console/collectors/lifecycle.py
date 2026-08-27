"""`LifecycleCollector` — `EPIC-007C`.

Reads the same four subsystems `WiringInspector.inspect_lifecycle()` already
reads, by the same attribute names — `registered_extensions`,
`initialized_extensions`, `ext.descriptor.name/enabled/dependencies`,
`services`, `started_services`, `jobs`, `job.job_func`, `job.next_run` — so
this collector and that inspector never drift about what those words mean.
"""

from __future__ import annotations

from typing import Any

from sagittarius_engine.extensions.audit.contracts import LifecycleState
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
        if self._extension_manager is not None:
            extensions_registered = len(self._extension_manager.registered_extensions)
            extensions_initialized = len(self._extension_manager.initialized_extensions)

        hosted_registered = 0
        hosted_started = 0
        if self._hosted_services is not None:
            hosted_registered = len(self._hosted_services.services)
            hosted_started = len(self._hosted_services.started_services)

        scheduler_jobs = 0
        scheduler_jobs_without_next_run = 0
        if self._scheduler is not None:
            jobs = self._scheduler.jobs
            scheduler_jobs = len(jobs)
            scheduler_jobs_without_next_run = sum(
                1 for job in jobs if getattr(job, "next_run", None) is None
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
        )
