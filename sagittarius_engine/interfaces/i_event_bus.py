from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from sagittarius_engine.domain.base_event import BaseEvent

E = TypeVar("E", bound=BaseEvent)


class IEventBus(ABC):
    """
    @brief Interface for the Event Bus (Pub/Sub mechanism).

    @details Allows different parts of the system to communicate loosely coupled.
    Supports both string-based event names and typed event classes inheriting from BaseEvent.

    @par Tutorial / Usage Example:
    @code
    # String-based:
    event_bus.on("user.created", on_user_created)
    event_bus.emit("user.created", new_user_obj)

    # Class-based (Typed):
    event_bus.on(UserCreatedEvent, lambda evt: print(evt.user_id))
    event_bus.emit(UserCreatedEvent(user_id=123))
    @endcode
    """

    @abstractmethod
    def emit(self, event_name_or_obj: str | BaseEvent | Any, data: Any = None) -> None:
        """
        @brief Publishes an event along with optional data.

        @param event_name_or_obj The event name or a BaseEvent object.
        @param data The data payload to pass to handlers if using event_name.
        """
        ...

    @abstractmethod
    def on(
        self, event_name_or_type: str | type[E] | Any, handler: Callable[..., Any]
    ) -> None:
        """
        @brief Subscribes a handler function to an event.

        @param event_name_or_type The event name or BaseEvent subclass type.
        @param handler The function to call when the event occurs.
        """
        ...

    @abstractmethod
    def off(
        self, event_name_or_type: str | type[E] | Any, handler: Callable[..., Any]
    ) -> None:
        """
        @brief Unsubscribes a handler function from an event.

        @param event_name_or_type The event name or BaseEvent subclass type.
        @param handler The function to remove.
        """
        ...

    def get_handlers(
        self, event_name_or_type: str | type[E] | Any
    ) -> tuple[Callable[..., Any], ...]:
        """
        @brief Returns registered handlers for an event.
        """
        return ()

    def subscriptions(self) -> Mapping[str, tuple[Callable[..., Any], ...]]:
        """
        @brief Every event name this bus currently has at least one handler for,
        mapped to those handlers.

        @details `get_handlers()` answers "who handles X" for an X the caller
        already knows. This answers "which X exist at all", which is the only
        way to reach a name nobody meant to register: a subscription to
        `"student.updatd"` can never be found by asking about
        `"student.updated"`. Joining this against
        `sagittarius_engine.domain.EventRegistry` is what turns a silent typo
        into a boot-time report (`EPIC-006`).

        @return Event name -> handlers, in no guaranteed order. Names whose
        handlers have all been removed via `off()` are omitted: an emptied name
        is not a subscription. The mapping is a snapshot; mutating the bus
        afterwards does not change it.

        @par Why this is concrete rather than abstract
        Mirrors `get_handlers()` directly above, and for the same reason: an
        `IEventBus` implemented outside this repository keeps working without
        changes. Declaring it abstract would break every such implementation at
        instantiation, and the usual alternative -- a base that raises
        `NotImplementedError` -- is forbidden outright by `code-rule.md` §L.

        The cost of a default is that a bus which does not override this is
        indistinguishable from a bus with nothing subscribed. A caller that
        must tell those apart can ask whether the method was overridden:

        @code
        introspectable = type(bus).subscriptions is not IEventBus.subscriptions
        @endcode

        Every bus shipped with this engine overrides it, and
        `tests/test_architecture.py::test_event_buses_implement_subscriptions`
        fails if a new one does not -- so the ambiguity never applies to a bus
        from this package.
        """
        return {}
