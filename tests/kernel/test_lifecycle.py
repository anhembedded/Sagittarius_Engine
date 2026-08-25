from unittest.mock import MagicMock

import pytest

from sagittarius_engine.kernel.lifecycle import (
    APP_READY_EVENT_NAME,
    EngineLifecycle,
    EngineState,
    InvalidStateTransition,
    Lifecycle,
)


def _lifecycle():
    """A lifecycle with a mock context, for the transitions that emit."""
    return EngineLifecycle(context=MagicMock())


def test_engine_lifecycle_states():
    lifecycle = EngineLifecycle(context=None)

    # Initial state. EPIC-006C: CREATED, not STOPPED — an engine that has never
    # booted and one that has been shut down used to be indistinguishable.
    assert lifecycle.state == EngineState.CREATED
    assert lifecycle.is_created is True
    assert lifecycle.is_stopped is False
    assert lifecycle.is_booting is False
    assert lifecycle.is_booted is False
    assert lifecycle.is_ready is False
    assert lifecycle.is_stopping is False

    lifecycle.set_booting()
    assert lifecycle.state == EngineState.BOOTING
    assert lifecycle.is_booting is True
    assert lifecycle.is_created is False

    lifecycle.set_booted()
    assert lifecycle.state == EngineState.BOOTED
    assert lifecycle.is_booted is True
    assert lifecycle.is_booting is False
    assert lifecycle.is_ready is False, "booted is not ready"

    lifecycle.set_stopping()
    assert lifecycle.state == EngineState.STOPPING
    assert lifecycle.is_stopping is True
    assert lifecycle.is_booted is False

    lifecycle.set_stopped()
    assert lifecycle.state == EngineState.STOPPED
    assert lifecycle.is_stopped is True
    assert lifecycle.is_stopping is False


def test_engine_state_enum_values():
    assert EngineState.CREATED.value == "created"
    assert EngineState.STOPPED.value == "stopped"
    assert EngineState.BOOTING.value == "booting"
    assert EngineState.BOOTED.value == "booted"
    assert EngineState.READY.value == "ready"
    assert EngineState.STOPPING.value == "stopping"


def test_lifecycle_initial_state():
    lifecycle = Lifecycle(context=None)
    assert lifecycle._state == "created"


# --------------------------------------------------------------- readiness


def test_ready_is_a_state_past_booted():
    lifecycle = _lifecycle()
    lifecycle.set_booting()
    lifecycle.set_booted()
    lifecycle.set_ready()

    assert lifecycle.is_ready is True
    assert lifecycle.is_booted is True, (
        "a caller asking 'did it boot' must not be told no once it is ready"
    )


def test_ready_emits_app_ready_exactly_once():
    lifecycle = _lifecycle()
    lifecycle.set_booting()
    lifecycle.set_booted()

    lifecycle.set_ready()
    lifecycle.set_ready()  # defensive second call

    emits = [
        call
        for call in lifecycle.context.event_bus.emit.call_args_list
        if call.args and call.args[0] == APP_READY_EVENT_NAME
    ]
    assert len(emits) == 1


def test_cannot_become_ready_without_booting():
    """Readiness after a failed boot is the lie this guard exists to prevent."""
    lifecycle = _lifecycle()

    with pytest.raises(InvalidStateTransition):
        lifecycle.set_ready()

    assert lifecycle.is_ready is False


def test_cannot_become_ready_while_still_booting():
    lifecycle = _lifecycle()
    lifecycle.set_booting()

    with pytest.raises(InvalidStateTransition):
        lifecycle.set_ready()


def test_a_failed_boot_can_still_be_shut_down():
    """Bootstrap cleans up and re-raises; the state must follow it down."""
    lifecycle = _lifecycle()
    lifecycle.set_booting()

    lifecycle.set_stopping()
    lifecycle.set_stopped()

    assert lifecycle.is_stopped is True


def test_stopping_an_engine_that_never_booted_is_allowed():
    lifecycle = _lifecycle()

    lifecycle.set_stopping()
    lifecycle.set_stopped()

    assert lifecycle.is_stopped is True


def test_a_same_state_transition_is_a_no_op_not_an_error():
    """Shutdown calls set_stopped() from more than one path."""
    lifecycle = _lifecycle()
    lifecycle.set_stopping()
    lifecycle.set_stopped()

    lifecycle.set_stopped()

    assert lifecycle.is_stopped is True


def test_a_stopped_engine_cannot_jump_straight_back_to_ready():
    lifecycle = _lifecycle()
    lifecycle.set_stopping()
    lifecycle.set_stopped()

    with pytest.raises(InvalidStateTransition) as excinfo:
        lifecycle.set_ready()

    assert "stopped" in str(excinfo.value) and "ready" in str(excinfo.value)


# ------------------------------------------------------------- when_ready


def test_when_ready_defers_until_ready():
    lifecycle = _lifecycle()
    lifecycle.set_booting()
    lifecycle.set_booted()
    calls = []

    lifecycle.when_ready(lambda: calls.append("ran"))
    assert calls == [], "not ready yet"

    lifecycle.set_ready()
    assert calls == ["ran"]


def test_when_ready_runs_immediately_for_a_late_arrival():
    """The health_check_requested.py:9 bug class, closed.

    A component subscribing to `app.ready` after it fired waits forever.
    """
    lifecycle = _lifecycle()
    lifecycle.set_booting()
    lifecycle.set_booted()
    lifecycle.set_ready()

    calls = []
    lifecycle.when_ready(lambda: calls.append("ran"))

    assert calls == ["ran"]


def test_when_ready_callbacks_run_once_and_in_order():
    lifecycle = _lifecycle()
    lifecycle.set_booting()
    lifecycle.set_booted()
    order = []

    lifecycle.when_ready(lambda: order.append(1))
    lifecycle.when_ready(lambda: order.append(2))

    lifecycle.set_ready()
    lifecycle.set_ready()

    assert order == [1, 2]


def test_when_ready_callbacks_run_before_the_event_is_emitted():
    """A subscriber that needs to be in place *for* app.ready still is."""
    lifecycle = _lifecycle()
    lifecycle.set_booting()
    lifecycle.set_booted()
    sequence = []

    lifecycle.context.event_bus.emit.side_effect = lambda *a, **k: sequence.append(
        "emit"
    )
    lifecycle.when_ready(lambda: sequence.append("callback"))

    lifecycle.set_ready()

    assert sequence == ["callback", "emit"]
