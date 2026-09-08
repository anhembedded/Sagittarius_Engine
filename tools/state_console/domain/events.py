"""Domain events `ConsoleConnectionExtension` emits — `EPIC-007E` §1.1.

Real `BaseEvent` subclasses, not polled flags: `EventRegistry` gains them the
same way any other domain event does, so `sagittarius-doctor` run against
this console's own `build_app()` reports on them like any other application
(`EPIC-007E` criterion 11).
"""

from __future__ import annotations

from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent
from sagittarius_engine.extensions.audit.contracts import StateSnapshot


@dataclass
class SnapshotReceived(BaseEvent):
    """@brief A fresh `StateSnapshot` arrived. Carries the parsed snapshot,
    never the raw wire envelope — a presenter has no business parsing JSON."""

    snapshot: StateSnapshot

    def __post_init__(self) -> None:
        # BaseEvent is not itself a dataclass, so @dataclass's generated
        # __init__ never calls it automatically (BUG-005) -- forgetting this
        # raises nothing here and only fails later, on first access to
        # .event_id/.occurred_on/.to_dict().
        BaseEvent.__init__(self)


class ConsoleAttached(BaseEvent):
    """@brief The websocket connection to the observed app is up. Distinct
    from "a snapshot arrived" — `EPIC-007E` §4's "attached, idle" state is
    real between this event and the first `SnapshotReceived`. No payload, so
    a plain subclass rather than a dataclass — nothing to declare."""

    event_name = "console.attached"


class ConsoleDetached(BaseEvent):
    """@brief The connection dropped, was refused, or was never established
    — an ordinary, expected state, never raised as an exception past this
    point."""

    event_name = "console.detached"

    def __init__(self, reason: str = "") -> None:
        super().__init__()
        self.reason = reason
