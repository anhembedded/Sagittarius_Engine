"""A menu shows related commands together, with one separator between
adjacent groups and never at either end or two in a row (MS `cmd-menus`;
the reference consumer's `BOT-157`)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMenuBar, QWidget

from sagittarius_engine.extensions.pyside_mvc import (
    ActionDescriptor,
    ActionRegistry,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_confirmation import (
    MessageBoxConfirmer,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.shell_menus import (
    TOOLBARS_MENU,
    VIEW_MENU,
    WINDOW_GROUP,
    MenuBarBuilder,
)

_CHART = ("&Chart",)
_SEPARATOR = "---"

type Extras = dict[tuple[str, ...], Sequence[QAction]]


def _layout(menu: QMenu) -> list[str]:
    return [
        _SEPARATOR if action.isSeparator() else action.text()
        for action in menu.actions()
    ]


def _assert_separators_only_between(menu: QMenu) -> None:
    layout = _layout(menu)
    assert layout, "an empty menu has nothing to check"
    assert layout[0] != _SEPARATOR
    assert layout[-1] != _SEPARATOR
    doubled = zip(layout[:-1], layout[1:], strict=True)
    assert all(pair != (_SEPARATOR, _SEPARATOR) for pair in doubled)


@pytest.fixture
def owner(qtbot) -> QWidget:
    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def registry(owner: QWidget) -> ActionRegistry:
    return ActionRegistry(owner, MessageBoxConfirmer())


def _builder(
    owner: QWidget, registry: ActionRegistry, extras: Extras | None = None
) -> MenuBarBuilder:
    known = extras or {}
    builder = MenuBarBuilder(
        QMenuBar(owner), registry, lambda: None, lambda path: known.get(path, ())
    )
    builder.build()
    return builder


def _command(action_id: str, text: str, group: str | None) -> ActionDescriptor:
    return ActionDescriptor(action_id, text, _CHART, group=group)


class TestGroups:
    def test_one_separator_between_adjacent_groups(
        self, owner: QWidget, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("candles", "&Candlestick", "mode"))
        registry.contribute(_command("equity", "&Equity curve", "mode"))
        registry.contribute(_command("volume", "&Volume", "layers"))
        registry.contribute(_command("live", "&Go live", "navigation"))

        menu = _builder(owner, registry).fill_now("&Chart")

        assert _layout(menu) == [
            "&Candlestick",
            "&Equity curve",
            _SEPARATOR,
            "&Volume",
            _SEPARATOR,
            "&Go live",
        ]

    def test_a_group_contributed_in_two_places_is_shown_together(
        self, owner: QWidget, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("candles", "&Candlestick", "mode"))
        registry.contribute(_command("volume", "&Volume", "layers"))
        registry.contribute(_command("equity", "&Equity curve", "mode"))

        menu = _builder(owner, registry).fill_now("&Chart")

        assert _layout(menu) == [
            "&Candlestick",
            "&Equity curve",
            _SEPARATOR,
            "&Volume",
        ]
        assert registry.menu_actions(_CHART, None) == tuple(
            action for action in menu.actions() if not action.isSeparator()
        )

    def test_commands_that_name_no_group_draw_no_separator(
        self, owner: QWidget, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("candles", "&Candlestick", None))
        registry.contribute(_command("volume", "&Volume", None))

        menu = _builder(owner, registry).fill_now("&Chart")

        assert _layout(menu) == ["&Candlestick", "&Volume"]

    def test_reopening_a_menu_does_not_pile_up_separators(
        self, owner: QWidget, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("candles", "&Candlestick", "mode"))
        registry.contribute(_command("volume", "&Volume", "layers"))
        builder = _builder(owner, registry)

        builder.fill_now("&Chart")
        menu = builder.fill_now("&Chart")

        assert _layout(menu) == ["&Candlestick", _SEPARATOR, "&Volume"]


class TestTheShellsExtras:
    def test_extras_after_commands_are_a_group_of_their_own(
        self, owner: QWidget, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("candles", "&Candlestick", "mode"))
        registry.contribute(_command("volume", "&Volume", "layers"))
        toggle = QAction("&Output", owner)

        menu = _builder(owner, registry, {_CHART: [toggle]}).fill_now("&Chart")

        _assert_separators_only_between(menu)
        assert _layout(menu)[-2:] == [_SEPARATOR, "&Output"]

    def test_a_menu_of_extras_alone_does_not_start_with_a_separator(
        self, owner: QWidget, registry: ActionRegistry
    ) -> None:
        # Tools always exists (Windows menu order); here nothing but the
        # shell's extras fills it.
        tools = ("&Tools",)
        builder = _builder(owner, registry, {tools: [QAction("&Output", owner)]})

        menu = builder.fill_now("&Tools")

        assert _layout(menu) == ["&Output"]


class TestSubmenus:
    """Review of the reference consumer's PR #374: Market's View menu put
    Toolbars › and Chart › in the chart-history group, after Back to live,
    and set Toolbars › apart from Status bar."""

    def test_a_submenu_is_not_drawn_into_the_last_group(
        self, owner: QWidget, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("live", "&Back to live", "history"))
        registry.contribute(
            ActionDescriptor("zoom", "Zoom &in", (*_CHART, "&Zoom"), group="zoom")
        )

        menu = _builder(owner, registry).fill_now("&Chart")

        assert _layout(menu) == ["&Back to live", _SEPARATOR, "&Zoom"]

    def test_toolbars_and_the_window_group_close_the_view_menu(
        self, owner: QWidget, registry: ActionRegistry
    ) -> None:
        view = (VIEW_MENU,)
        registry.contribute(
            ActionDescriptor("status", "Stat&us bar", view, group=WINDOW_GROUP)
        )
        registry.contribute(ActionDescriptor("mode", "&Market", view))
        registry.contribute(
            ActionDescriptor("bar", "&Mode bar", (VIEW_MENU, TOOLBARS_MENU))
        )
        registry.contribute(ActionDescriptor("live", "&Back to live", view, group="h"))
        registry.contribute(
            ActionDescriptor("zoom", "Zoom &in", (VIEW_MENU, "C&hart"), group="z")
        )
        toggle = QAction("&Watchlist", owner)

        menu = _builder(owner, registry, {view: [toggle]}).fill_now(VIEW_MENU)

        _assert_separators_only_between(menu)
        assert _layout(menu) == [
            "&Market",
            _SEPARATOR,
            "&Back to live",
            _SEPARATOR,
            "C&hart",
            _SEPARATOR,
            TOOLBARS_MENU,
            "Stat&us bar",
            _SEPARATOR,
            "&Watchlist",
        ]


def test_an_action_descriptor_names_no_group_by_default() -> None:
    assert ActionDescriptor("a", "&Apply", _CHART).group is None
