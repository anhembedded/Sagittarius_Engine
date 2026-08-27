"""`EnrolmentFlow` — a small, real `BaseStateMachine`, driven through one
illegal move for `EPIC-007D`'s demo.

Not a domain model this sample otherwise needs: it exists to give
`DemoFaultsExtension` something to drive legally and then illegally, the way
a real enrolment workflow would be driven by a real caller who forgot to
check `can_dispatch()` first.
"""

from __future__ import annotations

from enum import Enum, auto

from sagittarius_engine.extensions.fsm.exceptions import InvalidStateTransitionError
from sagittarius_engine.extensions.fsm.state_machine import BaseStateMachine


class EnrolmentState(Enum):
    DRAFT = auto()
    SUBMITTED = auto()
    APPROVED = auto()
    ENROLLED = auto()
    REJECTED = auto()


class EnrolmentFlow(BaseStateMachine[EnrolmentState]):
    """@brief `DRAFT -> SUBMITTED -> APPROVED -> ENROLLED`, with `REJECTED`
    reachable only from `SUBMITTED`. Nothing is a valid target from
    `ENROLLED` — it is terminal, which is exactly the state the demo attempts
    to leave."""

    def __init__(self) -> None:
        super().__init__(EnrolmentState.DRAFT)
        self.add_transition(EnrolmentState.DRAFT, EnrolmentState.SUBMITTED)
        self.add_transition(EnrolmentState.SUBMITTED, EnrolmentState.APPROVED)
        self.add_transition(EnrolmentState.SUBMITTED, EnrolmentState.REJECTED)
        self.add_transition(EnrolmentState.APPROVED, EnrolmentState.ENROLLED)


def drive_one_illegal_move(flow: EnrolmentFlow) -> InvalidStateTransitionError:
    """
    @brief Drives `flow` through a legal history to `ENROLLED`, then attempts
    to resubmit an already-enrolled student — illegal, since `ENROLLED` has no
    outgoing transitions.

    @return The `InvalidStateTransitionError` the illegal move raised.
        `REF-005`: `transition_to()` raises rather than returning `False`, so
        the caller — here, and any real one — must catch it, not check a
        return value.
    @raises AssertionError If the legal history itself fails, which would
        mean `EnrolmentFlow`'s own transition table is wrong, not that this
        function found the illegal move it was looking for.
    """
    assert flow.transition_to(EnrolmentState.SUBMITTED) is True
    assert flow.transition_to(EnrolmentState.APPROVED) is True
    assert flow.transition_to(EnrolmentState.ENROLLED) is True

    try:
        flow.transition_to(EnrolmentState.SUBMITTED)
    except InvalidStateTransitionError as exc:
        return exc
    raise AssertionError(
        "EnrolmentFlow accepted ENROLLED -> SUBMITTED — the transition table "
        "changed; drive_one_illegal_move's illegal move is no longer illegal."
    )
