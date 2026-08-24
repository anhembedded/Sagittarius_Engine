"""
@brief `EventEntry` — one row of the event catalog.

@details A value object describing an event type: its bus key, the class
carrying its payload (if it has one), and where that class is defined. Kept
apart from `EventRegistry`, which stores entries: a value object and the
collection that holds it are two different abstractions and do not share a
module.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass

#: Rendered in the catalog for an event that has no payload class of its own
#: (`"app.booted"`, whose payload is the `App` instance itself).
NO_CLASS_PLACEHOLDER = "—"


@dataclass(frozen=True)
class EventEntry:
    """
    @brief One catalog row: an event's bus key, its class (if it has one),
    and where it is defined.

    @details `payload_fields` is a computed property, not a stored field —
    load-bearing, not a style choice. A `BaseEvent` subclass registers itself
    from `__init_subclass__`, which fires while the `class X(BaseEvent):`
    statement is still building the class object, *before* an outer
    `@dataclass` decorator (if any) has attached `__dataclass_fields__` to
    it. Reading `dataclasses.fields()` at registration time — the first
    version of this class did exactly that — silently records an empty
    payload for every dataclass-decorated `BaseEvent` subclass forever,
    because this class is frozen and never re-reads the class afterward. A
    property re-reads `event_class` (whose fields are indeed present by the
    time anything actually asks) on every access instead, which is the only
    way to be correct for both registration paths.
    """

    event_name: str
    event_class: type | None
    module: str

    @property
    def payload_fields(self) -> tuple[str, ...]:
        if self.event_class is None or not is_dataclass(self.event_class):
            return ()
        return tuple(
            f.name for f in fields(self.event_class) if not f.name.startswith("_")
        )

    @property
    def qualname(self) -> str:
        if self.event_class is None:
            return NO_CLASS_PLACEHOLDER
        return self.event_class.__qualname__
