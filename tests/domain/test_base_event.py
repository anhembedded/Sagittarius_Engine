from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from sagittarius_engine.domain import BaseEvent
from sagittarius_engine.domain.i_domain_event import IDomainEvent


def test_base_event_initialization():
    event = BaseEvent()

    assert event.event_id is not None
    assert isinstance(event.event_id, str)

    assert event.occurred_on is not None
    assert isinstance(event.occurred_on, datetime)
    assert event.occurred_on.tzinfo == UTC


def test_base_event_to_dict():
    event = BaseEvent()

    data = event.to_dict()
    assert "event_id" in data
    assert "occurred_on" in data
    assert data["event_id"] == event.event_id
    assert data["occurred_on"] == event.occurred_on.isoformat()


def test_base_event_implements_idomain_event():
    event = BaseEvent()
    assert isinstance(event, IDomainEvent)


def test_idomain_event_cannot_be_instantiated():
    with pytest.raises(TypeError):
        IDomainEvent()


# --------------------------------------------------------------------------- #
# BUG-005 regression — inheriting BaseEvent from a @dataclass subclass used to
# leave every inherited member unset: `@dataclass` generates its own __init__
# and never calls super().__init__(), so `_event_id`/`_occurred_on` were never
# assigned and all three inherited members raised AttributeError on first use.
# --------------------------------------------------------------------------- #


@dataclass
class _ProgressEvent(BaseEvent):
    """A dataclass event with required fields — the shape every real consumer
    uses (`SingleSyncProgressEvent`, `BulkSyncProgressEvent` in the reference
    consuming app)."""

    symbol: str
    total: int


class _ManualInitEvent(BaseEvent):
    """A non-dataclass event with a hand-written `__init__` — the shape the
    engine's own events use (`HealthUpdatedEvent`, `SystemStateChangedEvent`,
    `TaskCompletedEvent`). Both shapes must keep working."""

    event_name = "manual.init"

    def __init__(self, payload: str) -> None:
        super().__init__()
        self.payload = payload


def test_dataclass_subclass_still_takes_positional_fields():
    event = _ProgressEvent("BTCUSDT", 10)

    assert event.symbol == "BTCUSDT"
    assert event.total == 10


def test_dataclass_subclass_gets_event_id_and_occurred_on():
    event = _ProgressEvent("BTCUSDT", 10)

    assert isinstance(event.event_id, str)
    assert event.event_id
    assert isinstance(event.occurred_on, datetime)
    assert event.occurred_on.tzinfo == UTC


def test_dataclass_subclass_event_ids_are_unique():
    first = _ProgressEvent("BTCUSDT", 10)
    second = _ProgressEvent("BTCUSDT", 10)

    assert first.event_id != second.event_id


def test_dataclass_subclass_to_dict_includes_metadata_and_payload():
    event = _ProgressEvent("BTCUSDT", 10)

    data = event.to_dict()

    assert data["symbol"] == "BTCUSDT"
    assert data["total"] == 10
    assert data["event_id"] == event.event_id
    assert data["occurred_on"] == event.occurred_on.isoformat()


def test_manual_init_subclass_still_gets_metadata():
    event = _ManualInitEvent("payload")

    assert event.payload == "payload"
    assert isinstance(event.event_id, str)
    assert event.occurred_on.tzinfo == UTC


def test_event_name_defaults_to_the_class_name():
    assert _ProgressEvent.event_name == "_ProgressEvent"
    assert _ProgressEvent("BTCUSDT", 10).event_name == "_ProgressEvent"


def test_event_name_is_not_overwritten_when_the_subclass_declares_one():
    assert _ManualInitEvent.event_name == "manual.init"


def test_metadata_stays_out_of_the_generated_repr():
    """`repr` is what shows up in logs — a UUID and a timestamp on every line
    would bury the payload the reader actually needs."""
    assert (
        repr(_ProgressEvent("BTCUSDT", 10))
        == "_ProgressEvent(symbol='BTCUSDT', total=10)"
    )


def test_two_events_with_the_same_payload_are_equal():
    """Regression for `EPIC-008F`: `_event_id`/`_occurred_on` must not join the
    generated `__eq__`.

    A fresh UUID per instance means that without `compare=False` no two events
    are ever equal, however identical their payloads — which silently breaks
    asserting an expected event, de-duplicating a queue, or diffing two runs.
    Equality is about *what happened*; the metadata describes *this
    occurrence*."""

    @dataclass
    class Failed(BaseEvent):
        reason: str

    first = Failed(reason="no data")
    second = Failed(reason="no data")

    assert first == second
    assert first != Failed(reason="something else")
    # Still individually identifiable — the metadata is present and unique,
    # it just does not participate in equality.
    assert first.event_id != second.event_id
    assert first.occurred_on is not None
