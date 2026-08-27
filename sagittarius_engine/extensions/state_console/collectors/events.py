"""`EventCollector` — `EPIC-007C`.

The declared ⋈ subscribed join `WiringInspector`'s check A2 already computes,
read the same way: `EventRegistry.all()` against `IEventBus.subscriptions()`.
"""

from __future__ import annotations

from sagittarius_engine.domain.event_registry import EventRegistry
from sagittarius_engine.extensions.audit.contracts import EventState
from sagittarius_engine.extensions.state_console.collector import ISnapshotSection
from sagittarius_engine.interfaces import IEventBus


class EventCollector(ISnapshotSection[tuple[EventState, ...]]):
    """
    @brief Every event name the engine knows about, declared or subscribed or
    both.

    @warning `emits` and `failures` are always `0`. Nothing in this engine
    counts *total* emits for a handled event — `RuntimeMonitor` (`R1`/`R2`)
    only ever counts the anomalous cases (unheard, or a handler that raised),
    and aggregating those per event name would mean reaching into
    `RuntimeMonitor`'s private failure map (its only public surface,
    `findings()`, returns human-formatted text, not structured counts) —
    exactly the reach-in `EPIC-006` criterion 2 forbids. Named here rather
    than faked; a public per-event counter on `RuntimeMonitor` is a small,
    separate addition if this is ever worth closing.
    """

    def __init__(self, bus: IEventBus) -> None:
        self._bus = bus

    def collect(self) -> tuple[EventState, ...]:
        declared = {entry.event_name: entry for entry in EventRegistry.all()}
        subscribed = dict(self._bus.subscriptions())
        names = set(declared) | set(subscribed)

        return tuple(
            EventState(
                name=name,
                module=declared[name].module if name in declared else "",
                handlers=tuple(
                    getattr(handler, "__qualname__", repr(handler))
                    for handler in subscribed.get(name, ())
                ),
                emits=0,
                failures=0,
                registered=name in declared,
            )
            for name in sorted(names)
        )
