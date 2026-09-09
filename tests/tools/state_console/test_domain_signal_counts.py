"""`count_signals` — `EPIC-008B` §2. Pure Python, no server, no Qt: every
counting rule is a small, independently testable claim about
`StateSnapshot` fields, not something worth exercising only indirectly
through a real websocket round-trip."""

from __future__ import annotations

from sagittarius_engine.extensions.audit.contracts import (
    DeadLetterEntry,
    EventState,
    LifecycleState,
    SignalsState,
    StateMachineState,
    StateSnapshot,
    TaskRecord,
)
from tools.state_console.domain.signal_counts import count_signals


def test_an_empty_snapshot_has_no_signals_anywhere():
    counts = count_signals(StateSnapshot())

    assert counts == {
        "events": 0,
        "container": 0,
        "tasks": 0,
        "signals": 0,
        "overview": 0,
    }


def test_events_counts_only_the_undeclared_ones():
    snapshot = StateSnapshot(
        events=(
            EventState(name="declared.one", registered=True),
            EventState(name="undeclared.one", registered=False),
            EventState(name="undeclared.two", registered=False),
        )
    )

    assert count_signals(snapshot)["events"] == 2


def test_container_is_always_zero_pending_richer_leak_detection():
    """§7.4's "scope leak suspected" needs a trend a single snapshot can't
    show -- see `signal_counts.py`'s own module docstring."""
    from sagittarius_engine.extensions.audit.contracts import ContainerState

    snapshot = StateSnapshot(container=ContainerState(open_scopes=999))

    assert count_signals(snapshot)["container"] == 0


def test_tasks_counts_failed_tasks_and_broken_scheduler_jobs():
    snapshot = StateSnapshot(
        tasks=(
            TaskRecord(id="1", state="failed"),
            TaskRecord(id="2", state="running"),
            TaskRecord(id="3", state="failed"),
        ),
        lifecycle=LifecycleState(scheduler_jobs_without_next_run=2),
    )

    assert count_signals(snapshot)["tasks"] == 4


def test_signals_counts_dead_letters_and_rejected_transitions():
    snapshot = StateSnapshot(
        signals=SignalsState(
            dead_letters=(
                DeadLetterEntry(event_name="a"),
                DeadLetterEntry(event_name="b"),
            ),
            state_machines=(
                StateMachineState(name="m1", rejected_count=3),
                StateMachineState(name="m2", rejected_count=0),
            ),
        )
    )

    assert count_signals(snapshot)["signals"] == 5


def test_a_missing_signals_section_counts_as_zero_not_a_crash():
    snapshot = StateSnapshot(signals=None)

    assert count_signals(snapshot)["signals"] == 0


def test_overview_is_the_sum_of_the_other_four():
    snapshot = StateSnapshot(
        events=(EventState(name="x", registered=False),),
        tasks=(TaskRecord(id="1", state="failed"),),
        signals=SignalsState(dead_letters=(DeadLetterEntry(event_name="a"),)),
    )

    counts = count_signals(snapshot)

    assert counts["overview"] == (
        counts["events"] + counts["container"] + counts["tasks"] + counts["signals"]
    )
    assert counts["overview"] == 3
