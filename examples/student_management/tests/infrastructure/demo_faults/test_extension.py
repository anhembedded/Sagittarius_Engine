"""`DemoFaultsExtension` against a real, booted app — `EPIC-007D` §2.2/§4.

Every one of `DemoFaultsExtension._seed()`'s seeds is asserted on directly:
the finding it is supposed to produce, or the object state it is supposed
to leave behind. Not counted here by number on purpose — `EPIC-008B`/`E`
already added three since this docstring's own original count went stale
once; `_seed()`'s own body is the actual list.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from examples.student_management.infrastructure.demo_faults.enrolment_flow import (
    EnrolmentState,
)
from examples.student_management.infrastructure.demo_faults.extension import (
    DemoFaultsExtension,
)
from examples.student_management.main import build_app
from sagittarius_engine.extensions.diagnostics.inspector import WiringInspector
from sagittarius_engine.extensions.fsm.exceptions import InvalidStateTransitionError
from sagittarius_engine.extensions.state_console import StateConsoleExtension


@pytest.fixture
def demo():
    return DemoFaultsExtension()


@pytest.fixture
def app(demo):
    # A file-based SQLite db, not :memory: -- DatabaseExtension's own session
    # crosses threads (AsyncRuntime), which :memory: does not tolerate. Same
    # reasoning as test_app_integration.py's own `app` fixture.
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        application = build_app(db_url=f"sqlite:///{db_path}", extra_extensions=[demo])
        yield application
        application.stop()


def _findings(report, check):
    return [f for f in report.findings if f.check == check]


# ------------------------------------------------------------------------ A2


def test_seeds_a2_a_typo_subscription_with_a_near_match_hint(app, demo):
    report = WiringInspector().inspect(bus=app.context.event_bus)

    # Two A2 findings exist on this bus: this typo, and a second, separate
    # A2 warning for `demo.student_deleted` (the R2 seed's own subscription,
    # which is a real string the registry does not know either -- just not
    # close enough to anything to be called a typo). Filtered to the one
    # this test is about.
    (finding,) = [
        f for f in _findings(report, "A2") if f.subject == "demo.roster_syncd"
    ]
    assert finding.severity == "error"
    assert finding.hint == 'did you mean "demo.roster_synced"?'


# ------------------------------------------------------------------------ R1


def test_seeds_r1_an_emit_with_nobody_listening(app, demo):
    findings = demo.runtime_monitor.findings()
    (finding,) = [f for f in findings if f.check == "R1"]
    assert finding.subject == "demo.roster_exported"


# ------------------------------------------------------------------------ R2


def test_seeds_r2_and_a_real_dead_letter(app, demo):
    findings = demo.runtime_monitor.findings()
    (finding,) = [f for f in findings if f.check == "R2"]
    assert "demo.student_deleted" in finding.subject

    assert demo.resilient_bus is not None
    dlq = demo.resilient_bus.get_dlq()
    assert len(dlq) == 1
    event_name, payload, _handler, exc, parked_at_ns = dlq[0]
    assert event_name == "demo.student_deleted"
    assert payload == {"student_id": "demo-0000"}
    assert isinstance(exc, KeyError)
    assert parked_at_ns > 0


# ------------------------------------------------------------------------ C2


def test_seeds_c2_an_unbound_plain_dependency(app, demo):
    report = WiringInspector().inspect(container=app.context.container)

    (finding,) = _findings(report, "C2")
    assert finding.severity == "warning"
    assert finding.subject == "_ReportService.clock"
    assert "_ReportSystemClock" in finding.message


# ------------------------------------------------------------------------ D3


def test_seeds_d3_a_job_with_no_next_run(app, demo):
    """Deliberately not read from `app.context.scheduler` -- see
    DemoFaultsExtension._seed_dead_scheduled_job()'s own docstring for why a
    job seeded dead there races the live background thread and is gone
    within milliseconds. `demo.dead_scheduled_job` is the stable artifact."""
    assert demo.dead_scheduled_job is not None
    assert demo.dead_scheduled_job.next_run is None

    fake_scheduler = SimpleNamespace(jobs=[demo.dead_scheduled_job])
    report = WiringInspector().inspect(scheduler=fake_scheduler)

    (finding,) = _findings(report, "D3")
    assert "nightly_report" in finding.subject
    assert finding.subject != "anonymous job"


# ------------------------------------------------------- ExclusiveAction slot


def test_seeds_a_held_exclusive_slot(app, demo):
    assert demo.exclusive_action is not None
    slot = demo.exclusive_action.held_slot()
    assert slot is not None
    assert slot.key == "demo-held-forever"
    assert slot.held_seconds >= 0.0


# --------------------------------------------------------------- EnrolmentFlow


def test_seeds_one_illegal_fsm_transition(app, demo):
    """`REF-005`: the rejection is an exception, not a `False` return."""
    assert demo.enrolment_flow is not None
    assert demo.enrolment_flow.current_state == EnrolmentState.ENROLLED
    assert isinstance(demo.rejected_transition, InvalidStateTransitionError)


# ----------------------------------------------------------- EPIC-008B subtask D


def test_seeds_a_real_open_scope_leak_past_the_fault_threshold(app, demo):
    """`reference/handoff.md` §7.4's own ">24" fault threshold for the
    Container screen's open-scopes plate -- this seed exists so that
    styling has something real to trigger against, not a hand-set number
    in a test fixture."""
    assert len(demo.leaked_scopes) == 30
    assert app.context.container.open_scope_count() >= 30


# ----------------------------------------------------------- EPIC-008B subtask E


def test_seeds_a_real_failed_task_with_a_real_stack(app, demo):
    """`EPIC-008E`'s own requirement ("a failed task's stack is readable
    after a click") needs a real failure to verify against, not a hand-set
    fixture -- this seed's task actually raises on a real worker thread."""
    assert demo.failed_task is not None
    try:
        demo.failed_task.future.result(timeout=2.0)
    except ValueError:
        pass

    # snapshot() -- what the console actually reads -- is the honest way to
    # observe the same failure this test just waited for.
    (entry,) = [t for t in app.context.tasks.snapshot() if t.id == demo.failed_task.id]
    assert entry.state.value == "failed"
    assert entry.error == "demo: enrolment PDF template not found"
    assert entry.error_type == "ValueError"
    assert entry.stack is not None and "ValueError" in entry.stack
    assert entry.thread is not None and entry.thread != ""


def test_seeds_a_real_active_scheduled_job(app, demo):
    """`EPIC-008E`'s Limits jobs table needs at least one real row with a
    real trigger and a genuine time to next fire."""
    assert demo.scheduled_job is not None
    assert demo.scheduled_job in app.context.scheduler.jobs
    assert demo.scheduled_job.next_run is not None


# ----------------------------------------------------------------- EPIC-007F


def test_with_a_console_attached_the_dlq_and_fsm_reach_a_real_snapshot():
    """`EPIC-007F` wiring: the console argument, not the demo faults
    themselves -- `test_seeds_r2_and_a_real_dead_letter`/
    `test_seeds_one_illegal_fsm_transition` already cover the faults
    directly. This is the one test asserting the two are actually
    connected, end to end through a real `StateConsoleExtension.collect()`."""
    console = StateConsoleExtension(port=0)
    demo = DemoFaultsExtension(console=console)
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        app = build_app(db_url=f"sqlite:///{db_path}", extra_extensions=[console, demo])
        try:
            snapshot = console.collect()
        finally:
            app.stop()

    assert snapshot.signals is not None

    (dead_letter,) = snapshot.signals.dead_letters
    assert dead_letter.event_name == "demo.student_deleted"
    assert dead_letter.exception_type == "KeyError"

    (machine,) = [
        m for m in snapshot.signals.state_machines if m.name == "EnrolmentFlow"
    ]
    assert machine.current_state == "ENROLLED"
    assert machine.rejected_count == 1
    assert any(
        t.rejected and t.from_state == "ENROLLED" and t.to_state == "SUBMITTED"
        for t in machine.transitions
    )


# ----------------------------------------------------------- every seed, once


def test_every_seed_produced_something(app, demo):
    """`EPIC-007D` criterion 2's own wording: at least one real entry per
    seed -- checked here as one assertion per seed rather than trusting the
    dedicated tests above to run."""
    report = WiringInspector().inspect(
        bus=app.context.event_bus, container=app.context.container
    )
    runtime_findings = demo.runtime_monitor.findings()

    assert _findings(report, "A2")
    assert [f for f in runtime_findings if f.check == "R1"]
    assert [f for f in runtime_findings if f.check == "R2"]
    assert demo.resilient_bus is not None and demo.resilient_bus.get_dlq()
    assert _findings(report, "C2")
    assert (
        demo.dead_scheduled_job is not None and demo.dead_scheduled_job.next_run is None
    )
    assert (
        demo.exclusive_action is not None
        and demo.exclusive_action.held_slot() is not None
    )
    assert demo.rejected_transition is not None
    assert len(demo.leaked_scopes) == 30
    assert demo.failed_task is not None
    assert demo.scheduled_job is not None and demo.scheduled_job.next_run is not None
