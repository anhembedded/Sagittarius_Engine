"""`ContainerCollector` — `EPIC-007C`.

`IContainer.registrations()` (type names, never instances, never triggers
construction — `EPIC-006A`) plus `IContainer.open_scope_count()`
(`EPIC-007B`), mapped into the wire shapes `EPIC-007A` defined.
"""

from __future__ import annotations

from sagittarius_engine.extensions.audit.contracts import (
    ContainerState,
    RegistrationState,
)
from sagittarius_engine.extensions.state_console.collector import ISnapshotSection
from sagittarius_engine.interfaces import IContainer


class ContainerCollector(ISnapshotSection[ContainerState]):
    """@brief The container's registry, plus the open-scope census."""

    def __init__(self, container: IContainer) -> None:
        self._container = container

    def collect(self) -> ContainerState:
        registrations = tuple(
            RegistrationState(
                abstract=abstract.__name__,
                concrete=registration.concrete.__name__
                if registration.concrete is not None
                else None,
                lifetime=registration.lifetime,
                instantiated=registration.instantiated,
            )
            for abstract, registration in sorted(
                self._container.registrations().items(), key=lambda kv: kv[0].__name__
            )
        )
        return ContainerState(
            registrations=registrations,
            open_scopes=self._container.open_scope_count(),
        )
