"""`ConsoleShellView` — `EPIC-007E` §3's navigation shell, rebuilt on the
new kit by `EPIC-008B` §2.

The sidebar and status band are QML now (`AppRail`/`LiveConnectionBand`,
hosted by `RailView`/`ConnectionBandView`), driven by `ShellPresenter` —
the same "screen content is QML, wired through a QmlHostView" shape
`OverviewView` etc. already use, just for shell-wide chrome instead of one
screen. `ConsoleShellView` itself stays a plain `QWidget`: it only lays the
pieces out and exposes the `bind_band`/`bind_rail`/`navigate_to` surface
`ShellPresenter` needs — see that class's own docstring.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sagittarius_engine.extensions.pyside_mvc.mvc.presenter_manager import (
    PresenterManager,
)
from sagittarius_engine.interfaces import IContainer
from tools.state_console.presentation.shell.connection_band_view import (
    ConnectionBandView,
)
from tools.state_console.presentation.shell.rail_view import RailView
from tools.state_console.presentation.shell.shell_presenter import ShellPresenter

#: Route name -> rail label, in display order.
SCREENS: tuple[tuple[str, str], ...] = (
    ("overview", "Overview"),
    ("events", "Events && wiring"),
    ("container", "Container"),
    ("tasks", "Tasks && threads"),
    ("signals", "Signals"),
)


class ConsoleShellView(QWidget):
    def __init__(self, container: IContainer, parent=None) -> None:
        super().__init__(parent)

        self._stack = QStackedWidget(self)
        self.manager = PresenterManager(container, self._stack)
        self._register_screens()

        self._band = ConnectionBandView(self)
        self._rail = RailView(self)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._rail)
        body.addWidget(self._stack, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._band)
        layout.addLayout(body, stretch=1)

        self.shell_presenter = ShellPresenter(self, container, SCREENS)

        self.navigate_to(SCREENS[0][0])

    def bind_band(self, view_model: Any) -> None:
        self._band.bind(view_model)

    def bind_rail(self, view_model: Any) -> None:
        self._rail.bind(view_model)

    def _register_screens(self) -> None:
        # Imported here rather than at module scope: every presenter/view
        # pair below transitively imports PySide6, and this module must
        # stay importable without it per EPIC-007E section 2 rule 2 /
        # pyside6_import_guard's module-scope check.
        from tools.state_console.presentation.container.container_presenter import (
            ContainerPresenter,
        )
        from tools.state_console.presentation.container.container_view import (
            ContainerView,
        )
        from tools.state_console.presentation.events.events_presenter import (
            EventsPresenter,
        )
        from tools.state_console.presentation.events.events_view import EventsView
        from tools.state_console.presentation.overview.overview_presenter import (
            OverviewPresenter,
        )
        from tools.state_console.presentation.overview.overview_view import (
            OverviewView,
        )
        from tools.state_console.presentation.signals.signals_presenter import (
            SignalsPresenter,
        )
        from tools.state_console.presentation.signals.signals_view import SignalsView
        from tools.state_console.presentation.tasks.tasks_presenter import (
            TasksPresenter,
        )
        from tools.state_console.presentation.tasks.tasks_view import TasksView

        self.manager.register("overview", OverviewPresenter, lambda: OverviewView())
        self.manager.register("events", EventsPresenter, lambda: EventsView())
        self.manager.register("container", ContainerPresenter, lambda: ContainerView())
        self.manager.register("tasks", TasksPresenter, lambda: TasksView())
        self.manager.register("signals", SignalsPresenter, lambda: SignalsView())

    def navigate_to(self, name: str) -> None:
        self.manager.navigate_to(name)
        self.shell_presenter.rail_view_model.set_active_section_id(name)

    def shutdown(self) -> None:
        self.shell_presenter.dispose()
        self.manager.shutdown()
