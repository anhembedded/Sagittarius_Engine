"""`ConsoleShellView` — `EPIC-007E` §3's navigation shell.

Plain `QWidget`/`QPushButton` sidebar, not QML: `kit.raw_primitive_guard`
only scans `.qml` files for raw `Button`/`CheckBox` use, and nothing here
needs a themed component more elaborate than a push button choosing which
screen is on top of the `QStackedWidget`. Screen content itself is still
QML, wired the same way `OverviewView` etc. already are.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sagittarius_engine.extensions.pyside_mvc.mvc.presenter_manager import (
    PresenterManager,
)
from sagittarius_engine.interfaces import IContainer

#: Route name -> sidebar label, in display order.
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

        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(0, 0, 0, 0)
        self._buttons: dict[str, QPushButton] = {}
        for name, label in SCREENS:
            button = QPushButton(label, self)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked, n=name: self.navigate_to(n))
            sidebar.addWidget(button)
            self._buttons[name] = button
        sidebar.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(sidebar)
        layout.addWidget(self._stack, stretch=1)

        self.navigate_to(SCREENS[0][0])

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
        for key, button in self._buttons.items():
            button.setChecked(key == name)

    def shutdown(self) -> None:
        self.manager.shutdown()
