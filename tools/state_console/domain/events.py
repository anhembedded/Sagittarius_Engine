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
    """@brief A connection that WAS attached (reached `ConsoleAttached` at
    least once) has since stopped — dropped, or cooperatively cancelled.
    Never emitted for an attempt that failed before ever attaching; that is
    `ConsoleFailed` (`EPIC-008B`) — an ordinary, expected state either way,
    never raised as an exception past this point."""

    event_name = "console.detached"

    def __init__(self, reason: str = "") -> None:
        super().__init__()
        self.reason = reason


class ConsoleConnecting(BaseEvent):
    """@brief A connection attempt to `uri` has started. No snapshot has
    ever been received from it — distinct from `ConsoleAttached`, which
    means the handshake actually succeeded (`EPIC-008B`)."""

    event_name = "console.connecting"

    def __init__(self, uri: str = "") -> None:
        super().__init__()
        self.uri = uri


class ConsoleFailed(BaseEvent):
    """@brief A connection attempt to `uri` failed outright — no snapshot
    was ever received from this address, which is what distinguishes this
    from `ConsoleDetached` (a connection that WAS working and then
    dropped). `kind` is one of `"malformed"` (the address itself does not
    parse — no socket was ever opened), `"refused"` (nothing is listening),
    `"rejected"` (the handshake was reached and refused, e.g. a bad/missing
    `?token=`), or `"unknown"` (a failure this extension can classify by
    *when* it happened — before ever attaching — but not by a more specific
    kind). `code` is a short machine-readable label
    (`"EINVAL"`/`"ECONNREFUSED"`/`"HTTP 401"`/...); `detail` is the
    human-readable exception text (`EPIC-008B`, `reference/handoff.md`
    §5)."""

    event_name = "console.failed"

    def __init__(
        self, *, kind: str = "unknown", code: str = "", detail: str = "", uri: str = ""
    ) -> None:
        super().__init__()
        self.kind = kind
        self.code = code
        self.detail = detail
        self.uri = uri
