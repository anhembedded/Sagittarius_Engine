from __future__ import annotations

from typing import Any

from sagittarius_engine.extensions.pyside_mvc import BasePresenter
from tools.state_console.domain.events import (
    ConsoleAttached,
    ConsoleDetached,
    SnapshotReceived,
)
from tools.state_console.presentation.container.container_view_model import (
    ContainerViewModel,
)
from tools.state_console.presentation.overview.overview_view_model import (
    ATTACHED_IDLE,
    ATTACHED_READING,
    NOT_ATTACHED,
)


class ContainerPresenter(BasePresenter):
    def __init__(self, view: Any, container: Any) -> None:
        super().__init__(view, container)
        self.view_model = ContainerViewModel()
        self.view.bind(self.view_model)
        self._connect_engine_events()

    def _connect_engine_events(self) -> None:
        self.subscribe(ConsoleAttached, self._on_attached)
        self.subscribe(ConsoleDetached, self._on_detached)
        self.subscribe(SnapshotReceived, self._on_snapshot)

    def _on_attached(self, _event: ConsoleAttached) -> None:
        self.view_model.set_connection_state(ATTACHED_IDLE)

    def _on_detached(self, event: ConsoleDetached) -> None:
        self.view_model.set_connection_state(NOT_ATTACHED)
        self.view_model.set_detach_reason(event.reason)

    def _on_snapshot(self, event: SnapshotReceived) -> None:
        self.view_model.set_connection_state(ATTACHED_READING)
        state = event.snapshot.container
        if state is None:
            self.view_model.set_container_state([], 0)
            return
        self.view_model.set_container_state(
            [
                {
                    "abstract": r.abstract,
                    "concrete": r.concrete or "?",
                    "lifetime": r.lifetime,
                    "instantiated": r.instantiated,
                }
                for r in state.registrations
            ],
            state.open_scopes,
        )
