"""`IEventBus.subscriptions()` — the enumeration half of the bus's introspection.

`get_handlers(name)` can only answer about a name the caller already has, which
makes it structurally incapable of finding a subscription nobody meant to make:
a handler bound to `"student.updatd"` is invisible to any question about
`"student.updated"`. `subscriptions()` enumerates instead, and `EPIC-006` joins
that against `EventRegistry` to turn the typo into a boot-time report.

The two decorator buses are the interesting cases and the reason this had to be
an interface method rather than a diagnostic reading `bus._handlers`.
"""

from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.infrastructure.event_bus.resilient_event_bus import (
    ResilientEventBus,
)
from sagittarius_engine.infrastructure.event_bus.thread_pool_event_bus import (
    ThreadPoolEventBus,
)


def _handler(data=None):
    return data


def _other(data=None):
    return data


def test_enumerates_names_get_handlers_cannot_be_asked_about():
    bus = MemoryEventBus()
    bus.on("student.added", _handler)
    bus.on("student.updatd", _other)  # deliberate typo — the case that matters

    names = set(bus.subscriptions())

    assert names == {"student.added", "student.updatd"}
    # The point: the typo is reachable by enumeration and by nothing else.
    assert bus.get_handlers("student.updated") == ()


def test_reports_every_handler_for_a_name():
    bus = MemoryEventBus()
    bus.on("evt", _handler)
    bus.on("evt", _other)

    assert bus.subscriptions()["evt"] == (_handler, _other)


def test_a_name_emptied_by_off_is_not_reported():
    """`off()` leaves an empty tuple behind rather than deleting the key."""
    bus = MemoryEventBus()
    bus.on("evt", _handler)
    bus.off("evt", _handler)

    assert bus.get_handlers("evt") == ()
    assert "evt" not in bus.subscriptions(), (
        "an emptied name is not a subscription; reporting it would make "
        "EPIC-006's registry diff claim a dead handler is live"
    )


def test_result_is_a_snapshot_not_a_live_view():
    bus = MemoryEventBus()
    bus.on("evt", _handler)

    snapshot = bus.subscriptions()
    bus.on("later", _other)

    assert "later" not in snapshot


def test_thread_pool_bus_reports_the_inner_bus_it_delegates_to():
    """It keeps no `_handlers` of its own — reading privates finds nothing."""
    bus = ThreadPoolEventBus()
    bus.on("evt", _handler)

    assert not hasattr(bus, "_handlers"), (
        "if this ever gains its own _handlers the test below stops proving "
        "delegation works"
    )
    assert bus.subscriptions() == {"evt": (_handler,)}


def test_resilient_bus_reports_the_handler_you_registered_not_its_wrapper():
    """The decorator registers a `resilient_wrapper`, never the caller's handler."""
    inner = MemoryEventBus()
    bus = ResilientEventBus(inner_bus=inner, max_retries=1)
    bus.on("evt", _handler)

    # What the inner bus actually holds is the wrapper, not `_handler`.
    (registered,) = inner.subscriptions()["evt"]
    assert registered is not _handler
    assert registered.__name__ == "resilient_wrapper"

    # What the decorator reports is the handler the caller subscribed.
    assert bus.subscriptions() == {"evt": (_handler,)}


def test_resilient_bus_passes_through_a_handler_subscribed_behind_its_back():
    """A subscription made on the inner bus directly has no wrapper mapping."""
    inner = MemoryEventBus()
    bus = ResilientEventBus(inner_bus=inner, max_retries=1)
    bus.on("wrapped", _handler)
    inner.on("direct", _other)

    reported = bus.subscriptions()

    assert reported == {"wrapped": (_handler,), "direct": (_other,)}, (
        "dropping an unmapped handler would hide a real subscription"
    )


def test_off_through_the_resilient_bus_clears_the_reported_subscription():
    inner = MemoryEventBus()
    bus = ResilientEventBus(inner_bus=inner, max_retries=1)
    bus.on("evt", _handler)
    bus.off("evt", _handler)

    assert "evt" not in bus.subscriptions()
