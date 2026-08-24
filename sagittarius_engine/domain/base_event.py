import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar

from sagittarius_engine.domain.event_registry import EventRegistry
from sagittarius_engine.domain.i_domain_event import IDomainEvent


@dataclass
class BaseEvent(IDomainEvent):
    """
    @brief Base class for domain events, providing an ID, a timestamp, and a
    stable `event_name`.

    @details Subclassing is optional — the event bus accepts any object — but a
    subclass gets four things for free: a unique `event_id`, a UTC
    `occurred_on`, an `event_name` that defaults to the class's qualified
    name, and automatic registration in `EventRegistry` (`event_registry.py`)
    — the catalog `scripts/generate_event_catalog.py` reads to produce
    `EVENT_CATALOG.md`, and the intended foundation for a planned
    engine-side event-audit tool. `event_name` is also the key `IEventBus`
    addresses the event by, so declaring one pins that key against a later
    class rename.

    Both subclass shapes are supported and covered by tests:

    - a `@dataclass` subclass declaring its own payload fields
      (`@dataclass class Progress(BaseEvent): symbol: str`), and
    - a plain subclass with a hand-written `__init__` that calls
      `super().__init__()` (the shape `HealthUpdatedEvent` and the audit
      events use).

    @par Two implementation details that are load-bearing — do not "simplify"
    either one:

    1. **The metadata fields are `kw_only`.** Without that, a subclass
       declaring a field with no default fails at class-creation time with
       `TypeError: non-default argument 'symbol' follows default argument`,
       because this base's fields carry defaults.
    2. **`event_id` / `occurred_on` are properties over private fields**, not
       public fields named directly after the `IDomainEvent` members. A public
       `event_id: str = field(default_factory=...)` looks equivalent and is
       not: `@dataclass` deletes the class attribute for a `default_factory`
       field and then calls `abc.update_abstractmethods()`, which re-marks the
       inherited abstract property as unimplemented — every instantiation then
       raises `TypeError: Can't instantiate abstract class`. Keeping concrete
       properties in the class body is what keeps `__abstractmethods__` empty.

    Both traps were found while fixing `BUG-005`, where a `@dataclass`
    subclass silently got no metadata at all: the generated `__init__` never
    called `super().__init__()`, so `_event_id`/`_occurred_on` were never
    assigned and all three inherited members raised `AttributeError` on first
    access.
    """

    #: Excluded from `repr` so a log line shows the event's payload rather
    #: than a UUID and a timestamp on every entry.
    _event_id: str = field(
        default_factory=lambda: str(uuid.uuid4()), kw_only=True, repr=False
    )
    _occurred_on: datetime = field(
        default_factory=lambda: datetime.now(UTC), kw_only=True, repr=False
    )

    #: The key `IEventBus` addresses this event by. Defaults to the subclass's
    #: `__qualname__`; declare it explicitly to keep a stable wire name across
    #: renames (e.g. `HealthUpdatedEvent.event_name = "health.updated"`).
    event_name: ClassVar[str] = "BaseEvent"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if "event_name" not in cls.__dict__:
            cls.event_name = cls.__qualname__
        EventRegistry.register(cls)

    @property
    def event_id(self) -> str:
        return self._event_id

    @property
    def occurred_on(self) -> datetime:
        return self._occurred_on

    def to_dict(self) -> dict:
        """
        @brief Returns a dictionary representation of the event.
        """
        data = self.__dict__.copy()
        if "_event_id" in data:
            data["event_id"] = data.pop("_event_id")
        if "_occurred_on" in data:
            data["occurred_on"] = data.pop("_occurred_on")

        data["occurred_on"] = self.occurred_on.isoformat()
        return data
