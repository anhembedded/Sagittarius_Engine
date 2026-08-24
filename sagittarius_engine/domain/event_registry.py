"""
@brief `EventRegistry` — the catalog of every event type the engine and its
consumers can emit, built automatically as event classes are defined.

@details
Two other designs were considered and rejected while planning
`Sagittarius_Elite_Warrior`'s `EPIC-008` (see that repo's
`Tasks/epics/EPIC-008_chuan_hoa_luong_event/DECISION_2026-08-24_event_architecture.md`
§4.6 for the full reasoning):

- **A hand-maintained enum mapping event names to classes.** Creates a second
  source of truth — adding an event means remembering to update two places,
  and it cannot represent this engine's own string-only lifecycle events
  (`"app.booted"`, `"extension.initializing"`, ...), which have no consuming
  application's dataclass to enumerate.
- **A hand-written catalog document with a "remember to update it" rule.**
  This is the exact failure mode `.agents/rules/doc-code-sync.md` exists to
  prevent: nothing forces the document to move when the code does.

This registry is neither: a `BaseEvent` subclass registers itself for free
via `__init_subclass__` (see `base_event.py`), and the engine's own
string-only lifecycle events register once, at their definition site, via
`register_named()` — see `kernel/events.py`, `runtime/hosted/events.py`,
`runtime/scheduler/events.py`, `runtime/tasks/events.py` for the pattern.
A generated `EVENT_CATALOG.md` and a test asserting it matches this registry
close the loop — see `scripts/generate_event_catalog.py` and
`tests/domain/test_event_registry.py`.

@par What this registry is not
It does not track *subscribers* — which handlers are registered against a
live `IEventBus` instance is runtime state tied to one running application,
not something a class-level, import-time registry can know. A consuming
app's own test suite is where "every event has at least one subscriber, or
is documented as intentionally unheard" belongs, checked against its actual
bus instance (`bus.get_handlers(event_name)`).
"""

from __future__ import annotations

from typing import ClassVar

from sagittarius_engine.domain.event_entry import EventEntry


class EventRegistry:
    """
    @brief Process-wide catalog of event types, keyed by `event_name`.

    @details A plain class attribute, not a singleton instance — an event
    type is a module-level definition, not per-application state, so there
    is exactly one registry per process, populated as event modules import.
    """

    _entries: ClassVar[dict[str, EventEntry]] = {}

    @classmethod
    def register(cls, event_class: type) -> None:
        """
        @brief Registers a `BaseEvent` subclass. Called automatically from
        `BaseEvent.__init_subclass__` — a consuming app never calls this
        directly.
        """
        event_name = getattr(event_class, "event_name", event_class.__qualname__)
        cls._entries[event_name] = EventEntry(
            event_name=event_name,
            event_class=event_class,
            module=event_class.__module__,
        )

    @classmethod
    def register_named(
        cls, event_name: str, event_class: type | None = None, *, module: str
    ) -> None:
        """
        @brief Registers an event that is addressed by a bare string on the
        bus rather than a `BaseEvent` subclass — this engine's own lifecycle
        events (`"app.booted"`, `"extension.initializing"`, ...).
        @param event_class The dataclass carrying the event's payload, if one
        exists (e.g. `ExtensionInitializing` for `"extension.initializing"`).
        `None` for an event with no payload class of its own.
        @param module Where the event is defined — required explicitly
        because a string has no `__module__` to read it from.
        """
        cls._entries[event_name] = EventEntry(
            event_name=event_name, event_class=event_class, module=module
        )

    @classmethod
    def all(cls) -> tuple[EventEntry, ...]:
        """@brief Every registered entry, sorted by `event_name`."""
        return tuple(sorted(cls._entries.values(), key=lambda e: e.event_name))

    @classmethod
    def get(cls, event_name: str) -> EventEntry | None:
        return cls._entries.get(event_name)

    @classmethod
    def clear(cls) -> None:
        """@brief Test-only: resets the registry to empty. Production code
        never calls this — event classes register once, at import time, and
        stay registered for the life of the process."""
        cls._entries.clear()
