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

import logging
from typing import ClassVar

from sagittarius_engine.domain.event_entry import EventEntry

#: Standard-library logger on purpose. Registration happens at *import* time,
#: inside `BaseEvent.__init_subclass__` — long before any container exists to
#: resolve an `ILogger` from, and this module is domain-layer, so reaching
#: into `infrastructure.logging` would invert the dependency.
_logger = logging.getLogger(__name__)


class EventRegistry:
    """
    @brief Process-wide catalog of event types, keyed by `event_name`.

    @details A plain class attribute, not a singleton instance — an event
    type is a module-level definition, not per-application state, so there
    is exactly one registry per process, populated as event modules import.

    @par Name collisions are reported, not silenced, and not fatal
    `event_name` defaults to the class's `__qualname__`, so two event classes
    that share a bare class name in different modules — a `Progress` or a
    `Completed` in two features — resolve to the same key. The later
    registration wins, which means the earlier event silently disappears from
    `all()` and therefore from the generated `EVENT_CATALOG.md`: a catalog
    that quietly omits an event is worse than no catalog, and defeats the very
    reason a registry was chosen over a hand-written document.

    Collisions are logged at WARNING rather than raised. Raising would turn a
    naming clash into an import-time crash that takes the whole application
    down for a documentation-quality problem, and could break a consuming app
    that already ships two same-named events. The warning names both classes
    and their modules so the fix — declaring an explicit `event_name` on one
    of them — is obvious from the log line alone.

    Re-registering the *same* class object is silent: module reloads and
    repeated imports are not collisions.
    """

    _entries: ClassVar[dict[str, EventEntry]] = {}

    @classmethod
    def _warn_on_shadowing(
        cls, event_name: str, event_class: type | None, module: str
    ) -> None:
        """@brief Logs a WARNING when `event_name` is already taken by a
        different event class. See the class docstring for why this warns
        instead of raising."""
        existing = cls._entries.get(event_name)
        if existing is None or existing.event_class is event_class:
            return
        _logger.warning(
            "Event name %r is already registered by %s.%s; %s.%s now replaces it "
            "in the registry and the earlier event will be missing from "
            "EVENT_CATALOG.md. Give one of them an explicit `event_name`.",
            event_name,
            existing.module,
            getattr(existing.event_class, "__qualname__", existing.event_class),
            module,
            getattr(event_class, "__qualname__", event_class),
        )

    @classmethod
    def register(cls, event_class: type) -> None:
        """
        @brief Registers a `BaseEvent` subclass. Called automatically from
        `BaseEvent.__init_subclass__` — a consuming app never calls this
        directly.
        """
        event_name = getattr(event_class, "event_name", event_class.__qualname__)
        cls._warn_on_shadowing(event_name, event_class, event_class.__module__)
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
        cls._warn_on_shadowing(event_name, event_class, module)
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
