"""The application window: Windows menu order, a mode bar over a stack of
hosts, View built from the showing mode, only the showing mode's commands live
(`EPIC-008D`; `ui-architecture.md` §9.5)."""

from __future__ import annotations

from functools import partial

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from sagittarius_engine.extensions.pyside_mvc import (
    OPTIONS_TITLE,
    ActionDescriptor,
    ActionRegistry,
    LogListModel,
    NavigationSource,
    OptionsDialog,
    OutputChannel,
    OutputPane,
    RegionHost,
    RegionKind,
    ShellMode,
    SurfaceDeclaration,
    WorkbenchShell,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_confirmation import (
    MessageBoxConfirmer,
)

_REGIONS = {"workspace": RegionKind.CENTRAL, "rail": RegionKind.DOCK_RIGHT}
_TRADE = ("T&rade",)


def _host(mode_id: str, *panels: str) -> RegionHost:
    host = RegionHost(SurfaceDeclaration(mode_id, frozenset(_REGIONS)), _REGIONS)
    host.place_widget("workspace", QLabel(mode_id))
    for title in panels:
        host.place_widget("rail", QLabel(title), title=title)
    return host


def _record(ran: list[str], mode_id: str, checked: bool) -> None:
    ran.append(mode_id)


def _titles(shell: WorkbenchShell) -> list[str]:
    return [action.text().replace("&", "") for action in shell.menuBar().actions()]


def _texts(shell: WorkbenchShell, menu: str) -> list[str]:
    return [action.text() for action in shell.menu(menu).actions() if action.text()]


@pytest.fixture
def registry(qtbot) -> ActionRegistry:
    owner = QWidget()
    qtbot.addWidget(owner)
    return ActionRegistry(owner, MessageBoxConfirmer())


@pytest.fixture
def shell(qtbot, registry: ActionRegistry) -> WorkbenchShell:
    window = WorkbenchShell(registry, application_name="Sample", about_text="A sample.")
    qtbot.addWidget(window)
    return window


def _two_modes(shell: WorkbenchShell, **guards) -> None:
    shell.add_mode(
        ShellMode("market", "&Market", _host("market", "Watchlist", "Indicators"))
    )
    shell.add_mode(
        ShellMode("bots", "&Bots", _host("bots", "Plan"), can_leave=guards.get("bots"))
    )


class TestTheMenuBar:
    def test_windows_order_with_the_application_menus_between_view_and_tools(
        self, shell: WorkbenchShell, registry: ActionRegistry
    ) -> None:
        registry.contribute(ActionDescriptor("trade.order", "&New order", _TRADE))
        _two_modes(shell)
        shell.finish_setup()

        assert _titles(shell) == [
            "File",
            "Edit",
            "View",
            "Trade",
            "Tools",
            "Window",
            "Help",
        ]

    def test_the_standard_commands_exist(self, shell: WorkbenchShell) -> None:
        _two_modes(shell)
        shell.finish_setup()

        assert _texts(shell, "&File") == ["E&xit"]
        assert _texts(shell, "&Tools") == ["&Options"]
        assert "&Reset layout" in _texts(shell, "&Window")
        assert _texts(shell, "&Help") == ["&About Sample"]

    def test_an_empty_menu_is_disabled_not_hidden(self, shell: WorkbenchShell) -> None:
        _two_modes(shell)
        shell.finish_setup()

        edit = next(a for a in shell.menuBar().actions() if a.text() == "&Edit")
        assert not edit.isEnabled()

    def test_unbound_commands_are_reported_by_finish_setup(
        self, shell: WorkbenchShell, registry: ActionRegistry
    ) -> None:
        registry.contribute(ActionDescriptor("trade.order", "&New order", _TRADE))
        _two_modes(shell)

        assert shell.finish_setup() == ("trade.order",)


class TestModes:
    def test_the_first_mode_shows_and_its_action_is_checked(self, shell) -> None:
        _two_modes(shell)
        shell.finish_setup()

        assert shell.current_mode == "market"
        assert shell.centralWidget().currentWidget().objectName() == "surface::market"
        modes = [
            a
            for a in shell.menu("&View").actions()
            if a.isCheckable() and a.isChecked()
        ]
        assert "&Market" in [a.text() for a in modes]

    def test_the_mode_shortcut_switches_mode(
        self, qtbot, shell: WorkbenchShell
    ) -> None:
        _two_modes(shell)
        shell.finish_setup()
        shell.show()
        with qtbot.waitActive(shell):
            shell.activateWindow()

        qtbot.keyClick(shell, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)

        assert shell.current_mode == "bots"

    def test_a_refused_leave_keeps_the_mode_and_its_check(
        self, shell: WorkbenchShell
    ) -> None:
        _two_modes(shell, bots=lambda source: source is NavigationSource.RESTORE)
        shell.finish_setup()
        shell.navigate("bots", NavigationSource.RESTORE)
        market = next(a for a in shell.menu("&View").actions() if a.text() == "&Market")

        market.trigger()

        assert shell.current_mode == "bots"
        assert not market.isChecked()

    def test_the_mode_bar_shows_icons_only(self, shell: WorkbenchShell) -> None:
        bar = shell.findChild(QWidget, "workbench::mode_bar")
        assert bar.toolButtonStyle() is Qt.ToolButtonStyle.ToolButtonIconOnly
        assert bar.orientation() is Qt.Orientation.Vertical


class TestOnlyTheShowingModesCommandsAreLive:
    def test_a_shared_key_reaches_only_the_showing_mode(
        self, qtbot, shell: WorkbenchShell, registry: ActionRegistry
    ) -> None:
        ran: list[str] = []
        for mode_id in ("market", "bots"):
            registry.contribute(
                ActionDescriptor(
                    f"{mode_id}.load",
                    "&Load",
                    _TRADE,
                    shortcut="Ctrl+L",
                    surface_id=mode_id,
                )
            )
            registry.bind(f"{mode_id}.load", partial(_record, ran, mode_id))
        _two_modes(shell)
        shell.finish_setup()
        shell.show()
        with qtbot.waitActive(shell):
            shell.activateWindow()

        qtbot.keyClick(shell, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
        shell.navigate("bots", NavigationSource.USER_INTENT)
        qtbot.keyClick(shell, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)

        assert ran == ["market", "bots"]


class TestView:
    def test_view_lists_the_showing_modes_panels_with_access_keys(
        self, shell: WorkbenchShell
    ) -> None:
        _two_modes(shell)
        shell.finish_setup()

        market_view = _texts(shell, "&View")
        shell.navigate("bots", NavigationSource.USER_INTENT)
        bots_view = _texts(shell, "&View")

        assert "&Watchlist" in market_view and "&Indicators" in market_view
        assert "Plan" not in " ".join(market_view)
        assert "&Plan" in bots_view and "&Watchlist" not in bots_view

    def test_reset_layout_brings_a_closed_panel_back(
        self, qtbot, shell: WorkbenchShell
    ) -> None:
        _two_modes(shell)
        shell.show()
        qtbot.waitExposed(shell)
        shell.finish_setup()
        watchlist = next(
            a for a in shell.menu("&View").actions() if a.text() == "&Watchlist"
        )
        watchlist.trigger()
        assert not watchlist.isChecked()

        assert shell.reset_layout()

        assert watchlist.isChecked()

    def test_the_toolbar_area_popup_lists_the_mode_bar(
        self, shell: WorkbenchShell
    ) -> None:
        popup = shell.createPopupMenu()
        assert popup is not None
        assert "Modes" in [action.text() for action in popup.actions()]


class TestStatusBarOutputAndOptions:
    def test_a_mode_status_widget_shows_only_in_its_mode(
        self, shell: WorkbenchShell
    ) -> None:
        _two_modes(shell)
        everywhere, bots_only = QLabel("Connected"), QLabel("2 running")
        shell.add_status_widget(everywhere)
        shell.add_status_widget(bots_only, mode_id="bots")
        shell.finish_setup()
        assert not bots_only.isVisibleTo(shell)

        shell.navigate("bots", NavigationSource.USER_INTENT)

        assert bots_only.isVisibleTo(shell) and everywhere.isVisibleTo(shell)

    def test_the_output_pane_is_docked_and_listed_in_window(
        self, shell: WorkbenchShell
    ) -> None:
        _two_modes(shell)
        pane = OutputPane()
        pane.add_channel(OutputChannel("sync", "Sync", LogListModel()))
        shell.set_output_pane(pane)
        shell.finish_setup()

        assert shell.dockWidgetArea(pane) is Qt.DockWidgetArea.BottomDockWidgetArea
        assert "&Output" in _texts(shell, "&Window")

    def test_tools_options_opens_the_options_dialog(
        self, shell: WorkbenchShell
    ) -> None:
        _two_modes(shell)
        shell.finish_setup()
        seen: list[str] = []

        def close_it() -> None:
            dialog = QApplication.activeModalWidget()
            assert isinstance(dialog, OptionsDialog)
            seen.append(dialog.windowTitle())
            dialog.reject()

        QTimer.singleShot(0, close_it)
        shell.show_options()

        assert seen == [OPTIONS_TITLE]


class TestRemembered:
    def test_geometry_and_mode_come_back_after_a_restart(
        self, qtbot, registry: ActionRegistry
    ) -> None:
        first = WorkbenchShell(registry, application_name="Sample", about_text="")
        qtbot.addWidget(first)
        _two_modes(first)
        first.finish_setup()
        # Inside the offscreen screen (800x600), which restoreGeometry clamps to.
        first.resize(640, 480)
        first.navigate("bots", NavigationSource.USER_INTENT)
        saved = first.capture_state()

        owner = QWidget()
        qtbot.addWidget(owner)
        second = WorkbenchShell(
            ActionRegistry(owner, MessageBoxConfirmer()),
            application_name="Sample",
            about_text="",
        )
        qtbot.addWidget(second)
        _two_modes(second)
        second.finish_setup()
        second.restore_state(saved)

        assert second.current_mode == "bots"
        assert second.size().width() == 640
