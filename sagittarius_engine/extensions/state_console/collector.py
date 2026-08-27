"""`ISnapshotSection[T]` — the shared contract behind `EPIC-007C`'s seven
collectors.

@par Why `@abstractmethod`, not a concrete no-op default
`IBusObserver`/`ITraceRecorder` use concrete no-op defaults because an
implementer may have partial interest — an observer that only cares about
failures should not have to write an empty `event_emitted`. No such case
exists here: every collector exists to provide exactly one thing, so a silent
no-op default would let a broken collector return `None` forever and read as
"not observed" rather than "not implemented". `ConfigSource`/`IFileStorage`/
`IStateStore`'s idiom — `ABC` + `@abstractmethod` — is the one that fits,
because it is the same shape: several implementations of one contract, each
expected to actually do the thing.

@par Not a third-party extension point
`StateSnapshot`'s seven sections are fixed by `EPIC-007A`'s schema; an eighth
collector would have nowhere on the wire to put its result. This interface
exists because `EPIC-007C` creates more files of one shape than any other
subtask in the epic and each should honour the same contract — not because a
consuming application is expected to implement its own.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ISnapshotSection[T](ABC):
    """@brief One section of a `StateSnapshot`, collected independently."""

    @abstractmethod
    def collect(self) -> T | None:
        """@brief The section's current value, or `None` if it cannot be
        observed."""
