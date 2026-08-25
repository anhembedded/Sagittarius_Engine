"""
@brief `HealthUpdatedEvent` — the result half of the health request/response
pair.

@details Moved out of `health_module.py` in `EPIC-008E`: an event and the
extension that emits it are different abstraction levels, and the consuming
app's `code-rule.md` §7 ("Abstraction-Level Separation") does not allow them
to share a file. `health_module` re-exports the name so the existing
`from ...health_module import HealthUpdatedEvent` imports keep working.
"""

from __future__ import annotations

from typing import Any

from sagittarius_engine.domain.base_event import BaseEvent


class HealthUpdatedEvent(BaseEvent):
    """
    @brief Emitted whenever health checks have been executed — once at boot,
    and once per `HealthCheckRequested` afterwards.

    @details A hand-written `__init__` rather than dataclass fields, kept
    deliberately: `status` is an opaque `dict` handed straight through from
    `HealthCheckQuery.execute()`, so there is nothing for `@dataclass` to buy
    here, and `BaseEvent` supports both subclass shapes (see its docstring).

    `event_name` is pinned to the wire string `"health.updated"` instead of
    letting `__init_subclass__` derive it from the class name — subscribers
    address it by that string, so a later class rename must not silently
    change the key.
    """

    event_name = "health.updated"

    def __init__(self, status: dict[str, Any]) -> None:
        super().__init__()
        self.status: dict[str, Any] = status
