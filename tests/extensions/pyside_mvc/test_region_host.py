"""Behavior tests for the region host (`EPIC-001D` objective 2; `TASK-043`
E2): every `RegionKind` renders onto the real `QMainWindow` part it claims,
and the host refuses the shapes that would look fine and be wrong. Mirrors
the reference consumer's own `test_workbench_surface.py` coverage, against
the generalized, opaque-`place` shape.
"""

from __future__ import annotations

import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QPushButton,
    QToolBar,
    QWidget,
    QWidgetAction,
)

from sagittarius_engine.extensions.pyside_mvc.runtime import (
    ContributionError,
    IRegionHost,
    RegionHost,
    RegionKind,
    SurfaceDeclaration,
)

_TRADING_PLACE_REGIONS = {
    "header": RegionKind.TOP_TOOLBAR,
    "context_bar": RegionKind.SECONDARY_TOOLBAR,
    "workspace": RegionKind.CENTRAL,
    "rail": RegionKind.DOCK_RIGHT,
    "console": RegionKind.DOCK_BOTTOM,
    "status_tile": RegionKind.STATUS_BAR,
    "modal": RegionKind.MODAL,
}


def _trading_surface() -> SurfaceDeclaration:
    return SurfaceDeclaration(
        surface_id="trading", accepts=frozenset(_TRADING_PLACE_REGIONS)
    )


@pytest.fixture
def trading(qapp, qtbot) -> RegionHost:
    host = RegionHost(_trading_surface(), _TRADING_PLACE_REGIONS)
    qtbot.addWidget(host)
    return host


class TestConstruction:
    def test_place_regions_must_cover_exactly_what_the_surface_accepts(
        self, qapp
    ) -> None:
        surface = SurfaceDeclaration(
            surface_id="trading", accepts=frozenset({"rail", "console"})
        )

        with pytest.raises(ContributionError, match="every accepted place"):
            RegionHost(surface, {"rail": RegionKind.DOCK_RIGHT})

    def test_place_regions_may_not_name_an_unaccepted_place(self, qapp) -> None:
        surface = SurfaceDeclaration(surface_id="trading", accepts=frozenset({"rail"}))

        with pytest.raises(ContributionError, match="every accepted place"):
            RegionHost(
                surface,
                {"rail": RegionKind.DOCK_RIGHT, "console": RegionKind.DOCK_BOTTOM},
            )


class TestIdentity:
    def test_it_reports_the_surface_it_hosts(self, trading: RegionHost) -> None:
        assert trading.surface_id == "trading"
        assert "rail" in trading.accepts()

    def test_it_nests_instead_of_drawing_its_own_window_frame(
        self, qapp, qtbot
    ) -> None:
        """A parent is not enough: `QMainWindow` sets the `Window` flag on
        itself, so nested in a page it would still draw its own title bar
        without `setWindowFlags(Qt.Widget)` clearing that flag set."""
        page = QWidget()
        qtbot.addWidget(page)

        nested = RegionHost(_trading_surface(), _TRADING_PLACE_REGIONS, page)

        assert nested.isWindow() is False
        assert nested.parent() is page

    def test_it_satisfies_the_region_host_port(self, trading: RegionHost) -> None:
        """`IRegionHost` is a `Protocol` and this class inherits nothing from
        it (`i_region_host.py`'s own docstring) — a structural contract with
        nothing checking it is documentation, so this is the check."""
        assert isinstance(trading, IRegionHost)


class TestThePlaceRegions:
    def test_central_becomes_the_central_widget(self, trading: RegionHost) -> None:
        chart = QLabel("chart")

        trading.place_widget("workspace", chart)

        assert trading.centralWidget() is chart

    def test_a_second_central_contribution_is_refused(
        self, trading: RegionHost
    ) -> None:
        trading.place_widget("workspace", QLabel("chart"))

        with pytest.raises(ContributionError, match="already has a central"):
            trading.place_widget("workspace", QLabel("second chart"))

    def test_top_and_secondary_toolbars_are_two_rows(self, trading: RegionHost) -> None:
        trading.place_action("header", QAction("&Start", trading))
        trading.place_action("context_bar", QAction("&Refresh", trading))

        top = trading.findChild(QWidget, f"{trading.objectName()}::top_toolbar")
        secondary = trading.findChild(
            QWidget, f"{trading.objectName()}::secondary_toolbar"
        )
        assert top is not None and secondary is not None
        assert top is not secondary
        assert trading.toolBarBreak(secondary) is True

    def test_a_dock_right_region_becomes_a_titled_dock_on_the_right(
        self, trading: RegionHost
    ) -> None:
        trading.place_widget("rail", QLabel("positions"), title="Positions")

        dock = trading.findChild(QWidget, f"{trading.objectName()}::rail::Positions")
        assert dock is not None
        assert dock.windowTitle() == "Positions"
        assert trading.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea

    def test_a_dock_bottom_region_goes_to_the_bottom_not_the_right(
        self, trading: RegionHost
    ) -> None:
        trading.place_widget("rail", QLabel("positions"), title="Positions")
        trading.place_widget("console", QLabel("log"), title="Log")

        rail = trading.findChild(QWidget, f"{trading.objectName()}::rail::Positions")
        console = trading.findChild(QWidget, f"{trading.objectName()}::console::Log")
        assert trading.dockWidgetArea(rail) == Qt.DockWidgetArea.RightDockWidgetArea
        assert trading.dockWidgetArea(console) == Qt.DockWidgetArea.BottomDockWidgetArea

    def test_two_docks_in_the_same_area_are_tabbed_not_stacked(
        self, trading: RegionHost
    ) -> None:
        trading.place_widget("rail", QLabel("positions"), title="Positions")
        trading.place_widget("rail", QLabel("orders"), title="Open orders")

        first = trading.findChild(QWidget, f"{trading.objectName()}::rail::Positions")
        assert trading.tabifiedDockWidgets(first)

    def test_an_untitled_dock_is_refused(self, trading: RegionHost) -> None:
        with pytest.raises(ContributionError, match="has no\n? *title"):
            trading.place_widget("rail", QLabel("positions"))

    def test_two_docks_with_one_title_are_refused(self, trading: RegionHost) -> None:
        trading.place_widget("rail", QLabel("a"), title="Positions")

        with pytest.raises(ContributionError, match="already has a panel"):
            trading.place_widget("rail", QLabel("b"), title="Positions")

    def test_a_status_bar_region_reaches_the_status_bar(
        self, trading: RegionHost
    ) -> None:
        pill = QLabel("WS: LIVE")

        trading.place_widget("status_tile", pill)

        assert pill.parent() is not None
        assert trading.statusBar().isAncestorOf(pill)


class TestWhatTheHostRefuses:
    def test_a_place_the_surface_does_not_accept(self, trading: RegionHost) -> None:
        with pytest.raises(ContributionError, match="cannot render 'dev_probe'"):
            trading.place_widget("dev_probe", QLabel("probe"), title="Probe")


class TestModals:
    def test_a_modal_is_kept_not_placed(self, trading: RegionHost) -> None:
        body = QLabel("order form")

        trading.place_widget("modal", body, title="Place order")

        assert trading.centralWidget() is None
        assert trading.modal_titles() == ("Place order",)

    def test_the_kept_dialog_carries_the_title_and_the_body(
        self, trading: RegionHost
    ) -> None:
        body = QLabel("order form")
        trading.place_widget("modal", body, title="Place order")

        dialog = trading.show_modal("Place order")

        assert dialog.windowTitle() == "Place order"
        assert dialog.isAncestorOf(body)

    def test_asking_for_a_dialog_nobody_contributed_says_what_there_is(
        self, trading: RegionHost
    ) -> None:
        trading.place_widget("modal", QLabel("form"), title="Place order")

        with pytest.raises(ContributionError, match="Place order"):
            trading.show_modal("Arm strategy")

    def test_an_untitled_modal_is_refused(self, trading: RegionHost) -> None:
        with pytest.raises(ContributionError, match="has no\n? *title"):
            trading.place_widget("modal", QLabel("form"))


class TestThePerspective:
    def test_a_saved_layout_comes_back(self, trading: RegionHost) -> None:
        trading.place_widget("rail", QLabel("positions"), title="Positions")
        trading.place_widget("console", QLabel("log"), title="Log")
        dock = trading.findChild(QWidget, f"{trading.objectName()}::console::Log")
        dock.hide()
        blob = trading.save_perspective()
        dock.show()

        assert trading.restore_perspective(blob) is True
        assert dock.isHidden()

    def test_an_empty_perspective_is_reported_not_raised(
        self, trading: RegionHost
    ) -> None:
        assert trading.restore_perspective(b"") is False

    def test_a_corrupt_perspective_leaves_the_default_layout_standing(
        self, trading: RegionHost, caplog
    ) -> None:
        trading.place_widget("rail", QLabel("positions"), title="Positions")
        dock = trading.findChild(QWidget, f"{trading.objectName()}::rail::Positions")

        with caplog.at_level(logging.INFO):
            assert trading.restore_perspective(b"not a QMainWindow state") is False

        assert not dock.isHidden()
        assert any("default layout" in record.message for record in caplog.records)


class TestToolbarsHoldActions:
    """A toolbar shows commands, and a command is a `QAction` (`EPIC-008B`)."""

    def test_an_action_lands_on_the_toolbar(self, trading: RegionHost) -> None:
        start = QAction("&Start", trading)

        trading.place_action("header", start)

        top = trading.findChild(QToolBar, f"{trading.objectName()}::top_toolbar")
        assert top is not None and start in top.actions()

    def test_a_bare_widget_on_a_toolbar_is_refused(
        self, qtbot, trading: RegionHost
    ) -> None:
        button = QPushButton("Start")
        qtbot.addWidget(button)
        with pytest.raises(ContributionError, match="holds actions, not widgets"):
            trading.place_widget("header", button)

    def test_a_migrating_consumer_may_opt_in_to_bare_toolbar_widgets(
        self, qtbot
    ) -> None:
        """A consumer whose toolbars still hold widgets opts in explicitly
        while it moves them to actions; the default stays the contract."""
        host = RegionHost(
            _trading_surface(), _TRADING_PLACE_REGIONS, legacy_toolbar_widgets=True
        )
        qtbot.addWidget(host)
        button = QPushButton("Start")

        host.place_widget("header", button)

        top = host.findChild(QToolBar, f"{host.objectName()}::top_toolbar")
        assert top is not None and top.isAncestorOf(button)
        assert host.legacy_toolbar_widgets

    def test_a_combo_box_wrapped_in_a_widget_action_is_accepted(
        self, trading: RegionHost
    ) -> None:
        wrapper = QWidgetAction(trading)
        wrapper.setDefaultWidget(QComboBox())

        trading.place_action("context_bar", wrapper)

        secondary = trading.findChild(
            QToolBar, f"{trading.objectName()}::secondary_toolbar"
        )
        assert secondary is not None and wrapper in secondary.actions()

    def test_a_widget_action_wrapping_a_button_is_refused(
        self, trading: RegionHost
    ) -> None:
        wrapper = QWidgetAction(trading)
        wrapper.setDefaultWidget(QPushButton("Start"))

        with pytest.raises(ContributionError, match="wraps a button"):
            trading.place_action("header", wrapper)

    def test_an_action_for_a_region_that_is_not_a_toolbar_is_refused(
        self, trading: RegionHost
    ) -> None:
        with pytest.raises(ContributionError, match="only a toolbar region"):
            trading.place_action("rail", QAction("&Start", trading))

    def test_toolbars_can_be_moved_and_hidden(self, trading: RegionHost) -> None:
        trading.place_action("header", QAction("&Start", trading))

        (toggle,) = trading.toolbar_toggle_actions()
        top = trading.findChild(QToolBar, f"{trading.objectName()}::top_toolbar")
        assert top is not None and top.isMovable()
        assert toggle is top.toggleViewAction()


class TestViewMenuAndPerspective:
    def test_every_dock_has_a_toggle_in_contribution_order(
        self, trading: RegionHost
    ) -> None:
        trading.place_widget("rail", QLabel("p"), title="Positions")
        trading.place_widget("console", QLabel("l"), title="Log")
        trading.place_widget("rail", QLabel("o"), title="Open orders")

        titles = [action.text() for action in trading.dock_toggle_actions()]

        assert titles == ["Positions", "Log", "Open orders"]

    def test_reset_puts_the_captured_default_back(
        self, qtbot, trading: RegionHost
    ) -> None:
        trading.place_widget("rail", QLabel("p"), title="Positions")
        trading.show()
        trading.capture_default_perspective()
        (toggle,) = trading.dock_toggle_actions()
        toggle.trigger()
        assert not toggle.isChecked()

        assert trading.reset_perspective() is True

        assert toggle.isChecked()

    def test_reset_without_a_captured_default_does_nothing(
        self, trading: RegionHost
    ) -> None:
        assert trading.reset_perspective() is False

    def test_a_saved_layout_of_another_version_is_not_applied(
        self, qapp, qtbot, caplog
    ) -> None:
        older = RegionHost(_trading_surface(), _TRADING_PLACE_REGIONS, layout_version=1)
        newer = RegionHost(_trading_surface(), _TRADING_PLACE_REGIONS, layout_version=2)
        qtbot.addWidget(older)
        qtbot.addWidget(newer)

        with caplog.at_level(logging.INFO, logger="App"):
            assert newer.restore_perspective(older.save_perspective()) is False

        assert "version 2" in caplog.text
