"""Domain events `ConsoleConnectionExtension` emits — `EPIC-007E` §1.1.

Real `BaseEvent` subclasses, not polled flags: `EventRegistry` gains them the
same way any other domain event does, so `sagittarius-doctor` run against
this console's own `build_app()` reports on them like any other application
(`EPIC-007E` criterion 11).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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


class ConsoleFailureKind(Enum):
    """@brief The closed set of ways a connection attempt can fail outright
    — same shape, same reasoning, as `runtime.tasks.background_task
    .TaskState`: a small fixed vocabulary is an `Enum` in this codebase,
    not a bare `str` a call site could misspell with nothing to catch it.
    """

    #: The address itself does not parse — no socket was ever opened.
    MALFORMED = "malformed"
    #: Nothing is listening at a syntactically valid address.
    REFUSED = "refused"
    #: The handshake was reached and refused (e.g. a bad/missing `?token=`).
    REJECTED = "rejected"
    #: Classifiable by *when* it happened (before ever attaching), not by a
    #: more specific kind — `code` carries the actual reason in this case.
    UNKNOWN = "unknown"


#: One default, machine-readable `code` per kind that has exactly one real
#: cause — `UNKNOWN` deliberately has none here, since its whole reason for
#: existing is that a single `code` can't be assumed; a caller emitting
#: `UNKNOWN` always supplies its own.
_DEFAULT_CODE_BY_KIND: dict[ConsoleFailureKind, str] = {
    ConsoleFailureKind.MALFORMED: "EINVAL",
    ConsoleFailureKind.REFUSED: "ECONNREFUSED",
    ConsoleFailureKind.REJECTED: "HTTP 401",
}


class ConsoleFailed(BaseEvent):
    """@brief A connection attempt to `uri` failed outright — no snapshot
    was ever received from this address, which is what distinguishes this
    from `ConsoleDetached` (a connection that WAS working and then
    dropped). `detail` is the human-readable exception text (`EPIC-008B`,
    `reference/handoff.md` §5).

    @param code A short machine-readable label
    (`"EINVAL"`/`"ECONNREFUSED"`/`"HTTP 401"`/...). Omit it for
    `MALFORMED`/`REFUSED`/`REJECTED` — each has exactly one real cause, so
    the code is filled in from `kind` and cannot drift from it by a
    copy-paste mistake at the call site. `UNKNOWN` has no such default and
    must always be given an explicit `code`.
    """

    event_name = "console.failed"

    def __init__(
        self,
        *,
        kind: ConsoleFailureKind = ConsoleFailureKind.UNKNOWN,
        code: str | None = None,
        detail: str = "",
        uri: str = "",
    ) -> None:
        super().__init__()
        if code is None:
            if kind not in _DEFAULT_CODE_BY_KIND:
                raise ValueError(
                    f"ConsoleFailed(kind={kind!r}) has no default code — "
                    "pass code= explicitly."
                )
            code = _DEFAULT_CODE_BY_KIND[kind]
        self.kind = kind
        self.code = code
        self.detail = detail
        self.uri = uri
