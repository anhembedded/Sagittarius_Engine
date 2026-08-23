import threading
from enum import Enum

import pytest

from sagittarius_engine.extensions.fsm import (
    DeclarativeStateMachine,
    InvalidStateTransitionError,
)


class OrderState(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderEvent(Enum):
    SUBMIT = "SUBMIT"
    FILL = "FILL"
    CANCEL = "CANCEL"
    REJECT = "REJECT"
    REFRESH = "REFRESH"


def test_declarative_fsm_initial_state() -> None:
    """FSM initializes with the specified initial state."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    assert fsm.current_state == OrderState.PENDING


def test_declarative_fsm_invalid_initial_state() -> None:
    """Non-enum initial states are rejected with TypeError."""
    with pytest.raises(TypeError):
        DeclarativeStateMachine("INVALID_STRING")  # type: ignore[type-var]


def test_add_event_transition_and_dispatch() -> None:
    """Single transition addition and event dispatching work as expected."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    fsm.add_event_transition(
        OrderState.PENDING, OrderEvent.SUBMIT, OrderState.SUBMITTED
    )

    assert fsm.can_dispatch(OrderEvent.SUBMIT) is True
    assert fsm.get_next_state(OrderEvent.SUBMIT) == OrderState.SUBMITTED

    success = fsm.dispatch(OrderEvent.SUBMIT)
    assert success is True
    assert fsm.current_state == OrderState.SUBMITTED


def test_load_matrix() -> None:
    """Bulk loading a declarative transition matrix works end-to-end."""
    matrix = {
        (OrderState.PENDING, OrderEvent.SUBMIT): OrderState.SUBMITTED,
        (OrderState.PENDING, OrderEvent.CANCEL): OrderState.CANCELLED,
        (OrderState.SUBMITTED, OrderEvent.FILL): OrderState.FILLED,
        (OrderState.SUBMITTED, OrderEvent.CANCEL): OrderState.CANCELLED,
        (OrderState.SUBMITTED, OrderEvent.REJECT): OrderState.REJECTED,
    }

    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    fsm.load_matrix(matrix)

    assert fsm.get_valid_events() == {OrderEvent.SUBMIT, OrderEvent.CANCEL}

    fsm.dispatch(OrderEvent.SUBMIT)
    assert fsm.current_state == OrderState.SUBMITTED
    assert fsm.get_valid_events() == {
        OrderEvent.FILL,
        OrderEvent.CANCEL,
        OrderEvent.REJECT,
    }

    fsm.dispatch(OrderEvent.FILL)
    assert fsm.current_state == OrderState.FILLED
    assert fsm.get_valid_events() == set()


def test_invalid_event_dispatch_raises_error_and_preserves_state() -> None:
    """Dispatching an invalid event raises InvalidStateTransitionError and preserves current state."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    fsm.add_event_transition(
        OrderState.PENDING, OrderEvent.SUBMIT, OrderState.SUBMITTED
    )

    assert fsm.can_dispatch(OrderEvent.FILL) is False

    with pytest.raises(InvalidStateTransitionError) as exc_info:
        fsm.dispatch(OrderEvent.FILL)

    assert exc_info.value.from_state == "PENDING"
    assert exc_info.value.event == "FILL"
    assert "Invalid transition from state 'PENDING' via event 'FILL'" in str(
        exc_info.value
    )
    assert fsm.current_state == OrderState.PENDING


def test_event_callback_on_event() -> None:
    """Event-specific callbacks are triggered with (old_state, new_state, event)."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    fsm.add_event_transition(
        OrderState.PENDING, OrderEvent.SUBMIT, OrderState.SUBMITTED
    )

    received_events: list[tuple[OrderState, OrderState, OrderEvent]] = []

    def on_submit_hook(old_st: OrderState, new_st: OrderState, ev: OrderEvent) -> None:
        received_events.append((old_st, new_st, ev))

    fsm.on_event(OrderEvent.SUBMIT, on_submit_hook)
    fsm.dispatch(OrderEvent.SUBMIT)

    assert len(received_events) == 1
    assert received_events[0] == (
        OrderState.PENDING,
        OrderState.SUBMITTED,
        OrderEvent.SUBMIT,
    )


def test_lifecycle_hooks_execution_order() -> None:
    """Hooks execute in exact order: on_exit -> global -> on_event -> on_enter."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    fsm.add_event_transition(
        OrderState.PENDING, OrderEvent.SUBMIT, OrderState.SUBMITTED
    )

    execution_log: list[str] = []

    fsm.on_exit(OrderState.PENDING, lambda: execution_log.append("on_exit_pending"))
    fsm.add_global_callback(
        lambda old_st, new_st: execution_log.append(
            f"global_{old_st.name}_to_{new_st.name}"
        )
    )
    fsm.on_event(
        OrderEvent.SUBMIT,
        lambda old_st, new_st, ev: execution_log.append(f"on_event_{ev.name}"),
    )
    fsm.on_enter(
        OrderState.SUBMITTED, lambda: execution_log.append("on_enter_submitted")
    )

    fsm.dispatch(OrderEvent.SUBMIT)

    assert execution_log == [
        "on_exit_pending",
        "global_PENDING_to_SUBMITTED",
        "on_event_SUBMIT",
        "on_enter_submitted",
    ]


def test_reentrancy_event_queue_sequential_processing() -> None:
    """Dispatching a secondary event inside an on_enter hook queues and executes FIFO."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    fsm.add_event_transition(
        OrderState.PENDING, OrderEvent.SUBMIT, OrderState.SUBMITTED
    )
    fsm.add_event_transition(OrderState.SUBMITTED, OrderEvent.FILL, OrderState.FILLED)

    execution_states: list[OrderState] = []

    # Inside SUBMITTED on_enter, trigger the next event FILL
    def auto_fill_on_submitted() -> None:
        execution_states.append(fsm.current_state)
        # Re-entrant dispatch call
        fsm.dispatch(OrderEvent.FILL)
        # Ensure that during this callback execution, state hasn't corrupted
        execution_states.append(fsm.current_state)

    fsm.on_enter(OrderState.SUBMITTED, auto_fill_on_submitted)
    fsm.on_enter(OrderState.FILLED, lambda: execution_states.append(fsm.current_state))

    fsm.dispatch(OrderEvent.SUBMIT)

    # After initial dispatch finished, FSM processed SUBMIT then FILL in FIFO order
    assert fsm.current_state == OrderState.FILLED
    assert execution_states == [
        OrderState.SUBMITTED,
        OrderState.SUBMITTED,
        OrderState.FILLED,
    ]


def test_reentrancy_queue_cleared_on_invalid_queued_event() -> None:
    """If an inner queued event fails validation, remaining queue is cleared and error raised."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    fsm.add_event_transition(
        OrderState.PENDING, OrderEvent.SUBMIT, OrderState.SUBMITTED
    )

    # Queue an invalid event from on_enter
    def bad_dispatch_on_submitted() -> None:
        fsm.dispatch(OrderEvent.SUBMIT)  # SUBMIT is invalid from SUBMITTED

    fsm.on_enter(OrderState.SUBMITTED, bad_dispatch_on_submitted)

    with pytest.raises(InvalidStateTransitionError) as exc_info:
        fsm.dispatch(OrderEvent.SUBMIT)

    assert exc_info.value.from_state == "SUBMITTED"
    assert exc_info.value.event == "SUBMIT"
    assert len(fsm._event_queue) == 0


def test_callback_exception_isolation_resilience() -> None:
    """Exceptions raised inside lifecycle hooks are safely caught and logged without aborting transitions."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    fsm.add_event_transition(
        OrderState.PENDING, OrderEvent.SUBMIT, OrderState.SUBMITTED
    )

    enter_called = False

    def failing_exit():
        raise RuntimeError("Exit hook failed intentionally")

    def failing_global(old_st, new_st):
        raise ValueError("Global hook failed intentionally")

    def failing_event(old_st, new_st, ev):
        raise KeyError("Event hook failed intentionally")

    def working_enter():
        nonlocal enter_called
        enter_called = True

    fsm.on_exit(OrderState.PENDING, failing_exit)
    fsm.add_global_callback(failing_global)
    fsm.on_event(OrderEvent.SUBMIT, failing_event)
    fsm.on_enter(OrderState.SUBMITTED, working_enter)

    # Dispatch should not raise and state must transition cleanly
    assert fsm.dispatch(OrderEvent.SUBMIT) is True
    assert fsm.current_state == OrderState.SUBMITTED
    assert enter_called is True


def test_type_validation_on_all_methods() -> None:
    """All methods reject non-enum arguments with TypeError."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)

    with pytest.raises(TypeError, match="from_state must be an instance of Enum"):
        fsm.add_event_transition("NOT_ENUM", OrderEvent.SUBMIT, OrderState.SUBMITTED)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="event must be an instance of Enum"):
        fsm.add_event_transition(OrderState.PENDING, "NOT_ENUM", OrderState.SUBMITTED)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="to_state must be an instance of Enum"):
        fsm.add_event_transition(OrderState.PENDING, OrderEvent.SUBMIT, "NOT_ENUM")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="event must be an instance of Enum"):
        fsm.on_event("NOT_ENUM", lambda o, n, e: None)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="event must be an instance of Enum"):
        fsm.can_dispatch("NOT_ENUM")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="event must be an instance of Enum"):
        fsm.get_next_state("NOT_ENUM")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="event must be an instance of Enum"):
        fsm.dispatch("NOT_ENUM")  # type: ignore[arg-type]


def test_self_transition_lifecycle() -> None:
    """State transitioning to itself properly triggers exit, event, and enter hooks."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    fsm.add_event_transition(OrderState.PENDING, OrderEvent.REFRESH, OrderState.PENDING)

    steps: list[str] = []
    fsm.on_exit(OrderState.PENDING, lambda: steps.append("exit"))
    fsm.on_event(OrderEvent.REFRESH, lambda o, n, e: steps.append("event"))
    fsm.on_enter(OrderState.PENDING, lambda: steps.append("enter"))

    assert fsm.dispatch(OrderEvent.REFRESH) is True
    assert fsm.current_state == OrderState.PENDING
    assert steps == ["exit", "event", "enter"]


def test_deep_reentrant_chain_fifo() -> None:
    """Multi-level nested events (A -> B -> C -> D) execute in sequential FIFO order."""

    class Step(Enum):
        S1 = 1
        S2 = 2
        S3 = 3
        S4 = 4

    class Ev(Enum):
        E1 = "E1"
        E2 = "E2"
        E3 = "E3"

    fsm = DeclarativeStateMachine[Step, Ev](Step.S1)
    fsm.add_event_transition(Step.S1, Ev.E1, Step.S2)
    fsm.add_event_transition(Step.S2, Ev.E2, Step.S3)
    fsm.add_event_transition(Step.S3, Ev.E3, Step.S4)

    order: list[int] = []

    # Real functions, not a `lambda: (a(), b())` tuple-comma trick -- that
    # shape doesn't actually return None (it returns a 2-tuple of the two
    # calls' results), which is both what on_enter's Callable[[], None]
    # contract requires and what mypy correctly flagged.
    def _enter_s2() -> None:
        order.append(2)
        fsm.dispatch(Ev.E2)

    def _enter_s3() -> None:
        order.append(3)
        fsm.dispatch(Ev.E3)

    fsm.on_enter(Step.S2, _enter_s2)
    fsm.on_enter(Step.S3, _enter_s3)
    fsm.on_enter(Step.S4, lambda: order.append(4))

    fsm.dispatch(Ev.E1)

    assert fsm.current_state == Step.S4
    assert order == [2, 3, 4]


def test_empty_matrix_queries() -> None:
    """Uninitialized / empty matrix queries return safe empty results without errors."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    assert fsm.get_valid_events() == set()
    assert fsm.get_next_state(OrderEvent.SUBMIT) is None
    assert fsm.can_dispatch(OrderEvent.SUBMIT) is False


def test_backward_compatibility_direct_transition_to() -> None:
    """Event transitions also synchronize base _allowed_transitions for transition_to()."""
    fsm = DeclarativeStateMachine[OrderState, OrderEvent](OrderState.PENDING)
    fsm.add_event_transition(
        OrderState.PENDING, OrderEvent.SUBMIT, OrderState.SUBMITTED
    )

    # Calling transition_to directly works
    assert fsm.transition_to(OrderState.SUBMITTED) is True
    assert fsm.current_state == OrderState.SUBMITTED

    # Invalid direct transition raises error
    with pytest.raises(InvalidStateTransitionError):
        fsm.transition_to(OrderState.CANCELLED)


def test_thread_safety_concurrent_dispatch() -> None:
    """Concurrent event dispatches across threads maintain valid states and don't deadlock."""

    class ToggleState(Enum):
        A = "A"
        B = "B"

    class ToggleEvent(Enum):
        TOGGLE = "TOGGLE"

    fsm = DeclarativeStateMachine[ToggleState, ToggleEvent](ToggleState.A)
    fsm.add_event_transition(ToggleState.A, ToggleEvent.TOGGLE, ToggleState.B)
    fsm.add_event_transition(ToggleState.B, ToggleEvent.TOGGLE, ToggleState.A)

    def spam_toggles() -> None:
        for _ in range(50):
            fsm.dispatch(ToggleEvent.TOGGLE)

    threads = [threading.Thread(target=spam_toggles) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert fsm.current_state in [ToggleState.A, ToggleState.B]
