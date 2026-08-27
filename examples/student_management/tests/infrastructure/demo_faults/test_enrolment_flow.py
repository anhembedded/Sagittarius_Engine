from examples.student_management.infrastructure.demo_faults.enrolment_flow import (
    EnrolmentFlow,
    EnrolmentState,
    drive_one_illegal_move,
)
from sagittarius_engine.extensions.fsm.exceptions import InvalidStateTransitionError


def test_legal_history_reaches_enrolled():
    flow = EnrolmentFlow()
    assert flow.transition_to(EnrolmentState.SUBMITTED) is True
    assert flow.transition_to(EnrolmentState.APPROVED) is True
    assert flow.transition_to(EnrolmentState.ENROLLED) is True
    assert flow.current_state == EnrolmentState.ENROLLED


def test_submitted_can_also_be_rejected():
    flow = EnrolmentFlow()
    flow.transition_to(EnrolmentState.SUBMITTED)
    assert flow.transition_to(EnrolmentState.REJECTED) is True


def test_enrolled_has_no_outgoing_transition():
    flow = EnrolmentFlow()
    flow.transition_to(EnrolmentState.SUBMITTED)
    flow.transition_to(EnrolmentState.APPROVED)
    flow.transition_to(EnrolmentState.ENROLLED)

    for target in EnrolmentState:
        if target is EnrolmentState.ENROLLED:
            continue
        try:
            flow.transition_to(target)
        except InvalidStateTransitionError:
            continue
        raise AssertionError(f"ENROLLED -> {target} should be illegal")


def test_drive_one_illegal_move_raises_not_returns_false():
    """`REF-005`: `transition_to()` raises `InvalidStateTransitionError` on an
    illegal move -- it has never returned `False`."""
    flow = EnrolmentFlow()

    exc = drive_one_illegal_move(flow)

    assert isinstance(exc, InvalidStateTransitionError)
    assert flow.current_state == EnrolmentState.ENROLLED
    assert str(exc) == "Invalid transition from 'ENROLLED' to 'SUBMITTED'."
