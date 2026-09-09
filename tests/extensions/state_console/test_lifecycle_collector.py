"""`LifecycleCollector` — `EPIC-007C`, extended by `EPIC-008B` §4's
`modules` field. A plain object standing in for `ExtensionManager` is
enough — the same fixture-lightness `test_signals_collector.py`'s own
docstring credits this collector for."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from sagittarius_engine.extensions.state_console.collectors.lifecycle import (
    LifecycleCollector,
)
from sagittarius_engine.kernel.lifecycle import EngineLifecycle, EngineState


def _extension(name):
    return SimpleNamespace(descriptor=SimpleNamespace(name=name))


def _fake_lifecycle(state: EngineState) -> EngineLifecycle:
    # MagicMock(), not SimpleNamespace(): EngineLifecycle.__init__ types its
    # context as IKernelContext, and mypy accepts a MagicMock stand-in for
    # any type -- the same choice test_lifecycle.py's own fixture makes.
    lifecycle = EngineLifecycle(context=MagicMock())
    lifecycle.state = state
    return lifecycle


def test_with_no_extension_manager_modules_is_empty():
    collector = LifecycleCollector(_fake_lifecycle(EngineState.READY))

    assert collector.collect().modules == ()


def test_modules_reports_every_registered_extension_by_name():
    manager = SimpleNamespace(
        registered_extensions=[_extension("A"), _extension("B")],
        initialized_extensions=[_extension("A"), _extension("B")],
    )
    collector = LifecycleCollector(
        _fake_lifecycle(EngineState.READY), extension_manager=manager
    )

    modules = collector.collect().modules
    assert [m.name for m in modules] == ["A", "B"]
    assert all(m.ready for m in modules)


def test_a_registered_but_not_yet_initialized_extension_reports_not_ready():
    """`EPIC-006` D1: a dependency that never arrives leaves an extension in
    `registered_extensions` forever, uninitialised -- `ready` must say so,
    matching `WiringInspector`'s own D1 check (by name, not object
    identity)."""
    manager = SimpleNamespace(
        registered_extensions=[_extension("A"), _extension("Stuck")],
        initialized_extensions=[_extension("A")],
    )
    collector = LifecycleCollector(
        _fake_lifecycle(EngineState.BOOTED), extension_manager=manager
    )

    modules = {m.name: m.ready for m in collector.collect().modules}
    assert modules == {"A": True, "Stuck": False}


def test_modules_order_matches_registration_order():
    manager = SimpleNamespace(
        registered_extensions=[_extension("Third"), _extension("First")],
        initialized_extensions=[],
    )
    collector = LifecycleCollector(
        _fake_lifecycle(EngineState.BOOTING), extension_manager=manager
    )

    assert [m.name for m in collector.collect().modules] == ["Third", "First"]


# --------------------------------------------------- EPIC-008E: jobs


def _job(name, trigger_description, next_run):
    return SimpleNamespace(
        fn=SimpleNamespace(__name__=name),
        trigger=SimpleNamespace(describe=lambda: trigger_description),
        next_run=next_run,
    )


def test_with_no_scheduler_jobs_is_empty():
    collector = LifecycleCollector(_fake_lifecycle(EngineState.READY))

    assert collector.collect().jobs == ()


def test_jobs_reports_name_trigger_and_a_positive_time_to_next_fire():
    from datetime import datetime, timedelta

    scheduler = SimpleNamespace(
        jobs=[
            _job("sync_roster", "every 0:05:00", datetime.now() + timedelta(minutes=5))
        ]
    )
    collector = LifecycleCollector(
        _fake_lifecycle(EngineState.READY), scheduler=scheduler
    )

    (job,) = collector.collect().jobs
    assert job.name == "sync_roster"
    assert job.trigger == "every 0:05:00"
    assert job.next_fire_seconds is not None
    assert job.next_fire_seconds > 0


def test_a_job_with_no_next_run_reports_next_fire_seconds_as_none():
    """The same `next_run is None` condition `scheduler_jobs_without_next_run`
    already names as broken -- WiringInspector's own D3 check."""
    scheduler = SimpleNamespace(jobs=[_job("dead_job", "every 0:01:00", None)])
    collector = LifecycleCollector(
        _fake_lifecycle(EngineState.READY), scheduler=scheduler
    )

    (job,) = collector.collect().jobs
    assert job.next_fire_seconds is None
