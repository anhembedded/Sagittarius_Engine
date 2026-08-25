"""
@brief `HealthCheckRequested` — the request half of the health
request/response pair (`EPIC-008E`).

@details
`HealthExtension.boot()` emits `HealthUpdatedEvent` exactly once, during
`app.boot()`. Any UI that subscribes later — which is every lazily-built
presenter, since the window is constructed after boot — has therefore
already missed it, and its subscription is dead code that never fires. Two
screens in `Sagittarius_Elite_Warrior` worked around this by fabricating the
event themselves: resolving `HealthCheckQuery` and calling their own handler
with a `HealthUpdatedEvent` they had constructed.

The alternative considered was a *sticky* bus that replays the last value to
a late subscriber. It was rejected (that app's
`EPIC-008`'s ADR §4.3): it adds a new capability to every bus in the engine
to serve one event, and it hands the subscriber a snapshot taken at boot
rather than the system's health right now.

A request/response pair needs no new bus capability at all — a screen asks,
the extension measures, and the answer travels the existing
`HealthUpdatedEvent` path to every listener:

```text
Presenter opens ──emit──► HealthCheckRequested
                                │
                    HealthExtension re-measures
                                │
                                └──emit──► HealthUpdatedEvent ──► every screen
```
"""

from __future__ import annotations

from sagittarius_engine.domain.base_event import BaseEvent


class HealthCheckRequested(BaseEvent):
    """
    @brief Asks `HealthExtension` to re-run its checks and publish a fresh
    `HealthUpdatedEvent`.

    @details Carries no payload: the request is the whole message, and the
    answer comes back over the bus as a separate event rather than as a
    return value — a bus handler has nowhere to return one to.

    Emitting this when no `HealthExtension` is booted is silently a no-op,
    the ordinary behaviour of a bus event with no subscribers. That is the
    right outcome for a health *request*: a caller asking after health should
    not crash the screen it was opened from.

    `event_name` is pinned to `"health.check_requested"` for the same reason
    `HealthUpdatedEvent` pins `"health.updated"` — subscribers address the
    wire string, so renaming the class must not move the key.
    """

    event_name = "health.check_requested"
