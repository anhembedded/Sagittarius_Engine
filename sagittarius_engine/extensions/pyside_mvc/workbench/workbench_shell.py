"""The top-level window: menu bar, mode bar, modes, status bar (`EPIC-008D`).

Qt Creator's shape (`ui-architecture.md` §9.5): a vertical mode bar on the
left switches a stack of `RegionHost`s, each a `QMainWindow` of its own with
its central widget, docks and toolbars. The shell owns what is the same in
every application — the Windows menu order, File → Exit, Tools → Options,
Window → Reset layout, Help → About, View built from the showing mode's docks
and toolbars, the remembered window — and the consumer owns which modes and
commands exist.

Only the showing mode's commands are live. Two modes may give one key to two
commands (`ActionRegistry` allows it), so the shell keeps the other modes'
actions off the window; their hosts are hidden, so their toolbars are too.

Wiring order: construct, contribute the consumer's commands to the same
`ActionRegistry`, `add_mode()` each mode, then `finish_setup()`, which builds
the menus, captures each mode's default layout and reports unbound commands.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from sagittarius_engine.extensions.pyside_mvc.runtime.region_host import RegionHost
from sagittarius_engine.extensions.pyside_mvc.workbench.action_descriptor import (
    ActionDescriptor,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_registry import (
    ActionRegistry,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.i_options_page import (
    IOptionsPage,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.navigation_service import (
    LeaveGuard,
    NavigationService,
    NavigationSource,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.options_dialog import (
    OptionsDialog,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import OutputPane
from sagittarius_engine.extensions.pyside_mvc.workbench.shell_menus import (
    FILE_MENU,
    HELP_MENU,
    TOOLBARS_MENU,
    TOOLS_MENU,
    VIEW_MENU,
    WINDOW_GROUP,
    WINDOW_MENU,
    MenuBarBuilder,
    Path,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.status_slot import StatusSlot
from sagittarius_engine.extensions.ui_state.state_scope import (
    JsonValue,
    StateData,
    StateScope,
)

#: The `ui_state` owner of the window's geometry and last mode.
SHELL_SCOPE_KEY = "workbench.shell"
#: Modes beyond the ninth get no Ctrl+digit shortcut.
_MAX_MODE_SHORTCUTS = 9
_GEOMETRY = "geometry"
_STATE = "state"
_MODE = "mode"
_STATUS_BAR = "status_bar"


@dataclass(frozen=True, slots=True)
class ShellMode:
    """One mode: its id, its View-menu text (with an access key), its host."""

    mode_id: str
    text: str
    host: RegionHost
    icon: QIcon | None = None
    can_leave: LeaveGuard | None = None


def _encode(blob: QByteArray) -> str:
    return base64.b64encode(bytes(blob.data())).decode("ascii")


def _decode(value: JsonValue) -> QByteArray | None:
    if not isinstance(value, str):
        return None
    try:
        return QByteArray(base64.b64decode(value, validate=True))
    except binascii.Error:
        return None


class WorkbenchShell(QMainWindow):
    """The application window. An `IStateContributor` for its geometry."""

    def __init__(
        self,
        registry: ActionRegistry,
        *,
        application_name: str,
        about_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("workbench::shell")
        self.setWindowTitle(application_name)
        self._registry = registry
        self._application_name = application_name
        self._about_text = about_text
        self._navigation = NavigationService(self)
        self._modes: dict[str, ShellMode] = {}
        self._mode_actions: dict[str, QAction] = {}
        self._status_slots: list[tuple[str | None, StatusSlot]] = []
        self._options_pages: list[IOptionsPage] = []
        self._output_pane: OutputPane | None = None
        self._stack = QStackedWidget(self)
        self.setCentralWidget(self._stack)
        self._mode_bar = self._build_mode_bar()
        self._mode_group = QActionGroup(self)
        self._mode_group.setExclusive(True)
        self._menus = MenuBarBuilder(
            self.menuBar(),
            registry,
            lambda: self._navigation.current,
            self._extra_actions,
        )
        self._contribute_standard_commands()
        self._navigation.mode_changed.connect(self._show_mode)
        self._navigation.navigation_refused.connect(self._keep_mode_checked)
        self.statusBar()

    # -- building ----------------------------------------------------------

    def _build_mode_bar(self) -> QToolBar:
        bar = QToolBar("Modes", self)
        bar.setObjectName("workbench::mode_bar")
        bar.setOrientation(Qt.Orientation.Vertical)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, bar)
        return bar

    def _contribute_standard_commands(self) -> None:
        commands = (
            (
                ActionDescriptor(
                    "workbench.exit",
                    "E&xit",
                    (FILE_MENU,),
                    shortcut=QKeySequence.StandardKey.Quit,
                ),
                self._on_exit,
            ),
            (
                ActionDescriptor(
                    "workbench.options",
                    "&Options",
                    (TOOLS_MENU,),
                    shortcut=QKeySequence.StandardKey.Preferences,
                ),
                self._on_options,
            ),
            (
                ActionDescriptor(
                    "workbench.reset_layout", "&Reset layout", (WINDOW_MENU,)
                ),
                self._on_reset_layout,
            ),
            (
                ActionDescriptor(
                    "workbench.about", f"&About {self._application_name}", (HELP_MENU,)
                ),
                self._on_about,
            ),
            (
                ActionDescriptor(
                    "workbench.status_bar",
                    "Stat&us bar",
                    (VIEW_MENU,),
                    checkable=True,
                    group=WINDOW_GROUP,
                ),
                self._on_status_bar,
            ),
            (
                ActionDescriptor(
                    "workbench.mode_bar",
                    "&Mode bar",
                    (VIEW_MENU, TOOLBARS_MENU),
                    checkable=True,
                ),
                self._on_mode_bar,
            ),
        )
        for descriptor, handler in commands:
            self._registry.contribute(descriptor)
            self._registry.bind(descriptor.action_id, handler)
        self._registry.action("workbench.status_bar").setChecked(True)
        mode_bar_check = self._registry.action("workbench.mode_bar")
        mode_bar_check.setChecked(True)
        # The toolbar-area popup and restoreState() hide the bar without this
        # action; its own toggle action follows every one of them.
        self._mode_bar.toggleViewAction().toggled.connect(mode_bar_check.setChecked)

    def add_mode(self, mode: ShellMode) -> None:
        """Adds a mode: a page of the stack, a mode-bar button and a View
        item with Ctrl+<n> for the first nine."""
        if mode.mode_id in self._modes:
            raise ValueError(f"mode {mode.mode_id!r} is already added")
        number = len(self._modes) + 1
        shortcut = f"Ctrl+{number}" if number <= _MAX_MODE_SHORTCUTS else None
        descriptor = ActionDescriptor(
            f"workbench.mode.{mode.mode_id}",
            mode.text,
            (VIEW_MENU,),
            shortcut=shortcut,
            checkable=True,
        )
        action = self._registry.contribute(descriptor)
        if mode.icon is not None:
            action.setIcon(mode.icon)
        self._mode_group.addAction(action)
        self._mode_bar.addAction(action)
        self._modes[mode.mode_id] = mode
        self._mode_actions[mode.mode_id] = action
        self._stack.addWidget(mode.host)
        self._registry.bind(
            descriptor.action_id, partial(self._on_mode_clicked, mode.mode_id)
        )
        self._navigation.register(mode.mode_id, mode.can_leave)

    def add_status_widget(self, widget: QWidget, mode_id: str | None = None) -> None:
        """A permanent status-bar widget, shown in every mode or in one.

        The shell decides only the mode: the widget stays its owner's to
        show and hide (`StatusSlot`, `BUG-021`)."""
        slot = StatusSlot(widget, self.statusBar())
        self.statusBar().addPermanentWidget(slot)
        self._status_slots.append((mode_id, slot))
        self._sync_status_widgets()

    def add_options_page(self, page: IOptionsPage) -> None:
        self._options_pages.append(page)

    def set_output_pane(self, pane: OutputPane) -> None:
        """Docks the one Output pane at the bottom; Window lists its toggle."""
        if self._output_pane is not None:
            raise ValueError("the shell already has an Output pane")
        self._output_pane = pane
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, pane)

    def finish_setup(self) -> tuple[str, ...]:
        """Builds the menus, captures each mode's default layout, makes the
        current mode's commands live, and returns the unbound command ids."""
        self._menus.build()
        for mode in self._modes.values():
            mode.host.capture_default_perspective()
        current = self._navigation.current
        if current is not None:
            self._show_mode(current)
        return self._registry.report_unbound()

    # -- navigating ---------------------------------------------------------

    @property
    def navigation(self) -> NavigationService:
        return self._navigation

    @property
    def current_mode(self) -> str | None:
        return self._navigation.current

    def navigate(self, mode_id: str, source: NavigationSource) -> bool:
        return self._navigation.navigate(mode_id, source)

    def _show_mode(self, mode_id: str) -> None:
        mode = self._modes[mode_id]
        self._stack.setCurrentWidget(mode.host)
        self._mode_actions[mode_id].setChecked(True)
        self._menus.empty_all()
        self._sync_live_actions(mode_id)
        self._sync_status_widgets()
        self._menus.refresh_enabled()

    def _keep_mode_checked(self, kept: str, refused: str) -> None:
        self._mode_actions[kept].setChecked(True)

    def _sync_live_actions(self, mode_id: str) -> None:
        for scope, action in self._registry.scoped_actions():
            if scope is None or scope == mode_id:
                self.addAction(action)
            else:
                self.removeAction(action)

    def _sync_status_widgets(self) -> None:
        current = self._navigation.current
        for scope, slot in self._status_slots:
            slot.set_in_scope(scope is None or scope == current)

    # -- the standard commands --------------------------------------------------

    def _on_exit(self, checked: bool) -> None:
        self.close()

    def _on_options(self, checked: bool) -> None:
        self.show_options()

    def _on_reset_layout(self, checked: bool) -> None:
        self.reset_layout()

    def _on_about(self, checked: bool) -> None:
        self.show_about()

    def _on_status_bar(self, checked: bool) -> None:
        self.statusBar().setVisible(checked)

    def _on_mode_bar(self, checked: bool) -> None:
        self._mode_bar.setVisible(checked)

    def _on_mode_clicked(self, mode_id: str, checked: bool) -> None:
        self.navigate(mode_id, NavigationSource.USER_INTENT)

    def show_options(self) -> OptionsDialog:
        """Opens Tools → Options modally and returns the dialog once closed.
        The dialog is deleted when the event loop next runs: each open builds
        a new one, and a closed one kept alive would keep listening to its
        pages (`BUG-018`)."""
        dialog = OptionsDialog(self._options_pages, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.exec()
        return dialog

    def show_about(self) -> None:
        QMessageBox.about(self, f"About {self._application_name}", self._about_text)

    def reset_layout(self) -> bool:
        current = self._navigation.current
        if current is None:
            return False
        return self._modes[current].host.reset_perspective()

    def menu(self, title: str) -> QMenu:
        """A top-level menu, filled for the current mode as opening it would."""
        return self._menus.fill_now(title)

    def _extra_actions(self, path: Path) -> Sequence[QAction]:
        current = self._navigation.current
        host = self._modes[current].host if current is not None else None
        if path == (VIEW_MENU,) and host is not None:
            return host.dock_toggle_actions()
        if path == (VIEW_MENU, TOOLBARS_MENU) and host is not None:
            return host.toolbar_toggle_actions()
        if path == (WINDOW_MENU,) and self._output_pane is not None:
            return (self._output_pane.toggleViewAction(),)
        return ()

    # -- IStateContributor (structural) -------------------------------------

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key=SHELL_SCOPE_KEY)

    def capture_state(self) -> StateData:
        return {
            _GEOMETRY: _encode(self.saveGeometry()),
            _STATE: _encode(self.saveState()),
            _MODE: self._navigation.current,
            _STATUS_BAR: not self.statusBar().isHidden(),
        }

    def restore_state(self, data: StateData) -> None:
        geometry = _decode(data.get(_GEOMETRY))
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = _decode(data.get(_STATE))
        if state is not None:
            self.restoreState(state)
        status_bar = data.get(_STATUS_BAR)
        if isinstance(status_bar, bool):
            self.statusBar().setVisible(status_bar)
            self._registry.action("workbench.status_bar").setChecked(status_bar)
        mode = data.get(_MODE)
        if isinstance(mode, str) and mode in self._modes:
            self.navigate(mode, NavigationSource.RESTORE)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        current = self._navigation.current
        guard = self._modes[current].can_leave if current is not None else None
        if guard is not None and not guard(NavigationSource.USER_INTENT):
            event.ignore()
            return
        super().closeEvent(event)
