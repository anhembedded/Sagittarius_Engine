"""One `QAction` per command, validated against every other command
(`EPIC-008C`)."""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QWidget

from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ActionConfirmation,
    ActionDeclarationError,
    ActionDescriptor,
    ActionRegistry,
    shortcut_problem,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    action_registry as action_registry_module,
)

_TRADE = ("T&rade",)
_STOP = ActionConfirmation(
    title="Stop bot",
    consequence="Its resting orders are cancelled.",
    accept_text="Stop bot",
)


class _AnsweringConfirmer:
    """An `IActionConfirmer` that answers as told and records each question."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[ActionConfirmation] = []

    def confirm(self, parent: QWidget | None, confirmation: ActionConfirmation) -> bool:
        self.asked.append(confirmation)
        return self.answer


class _Presenter(QObject):
    can_start = Signal(bool)
    is_live = Signal(bool)


def _reserved_free_key() -> str | None:
    portable = QKeySequence.SequenceFormat.PortableText
    for standard in QKeySequence.StandardKey:
        for binding in QKeySequence.keyBindings(standard):
            key = binding.toString(portable)
            if shortcut_problem(key) is None:
                return key
    return None


def _command(action_id: str, text: str, **fields: object) -> ActionDescriptor:
    return ActionDescriptor(
        action_id=action_id,
        text=text,
        menu_path=fields.pop("menu_path", _TRADE),  # type: ignore[arg-type]
        **fields,  # type: ignore[arg-type]
    )


@pytest.fixture
def owner(qtbot) -> QWidget:
    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def confirmer() -> _AnsweringConfirmer:
    return _AnsweringConfirmer(answer=True)


@pytest.fixture
def registry(owner: QWidget, confirmer: _AnsweringConfirmer) -> ActionRegistry:
    return ActionRegistry(owner, confirmer)


class TestRefusals:
    def test_a_duplicate_id(self, registry: ActionRegistry) -> None:
        registry.contribute(_command("trade.start", "&Start"))
        with pytest.raises(ActionDeclarationError, match="already contributed"):
            registry.contribute(_command("trade.start", "S&top"))

    def test_two_commands_on_one_key_in_one_scope(
        self, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("a", "&Start", shortcut="F9"))
        with pytest.raises(ActionDeclarationError, match="both bind"):
            registry.contribute(_command("b", "S&top", shortcut="F9"))

    def test_a_global_command_conflicts_with_every_mode(
        self, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("a", "&Start", shortcut="F8"))
        with pytest.raises(ActionDeclarationError, match="both bind"):
            registry.contribute(
                _command("b", "S&top", shortcut="F8", surface_id="bots")
            )

    def test_two_modes_may_share_a_key(self, registry: ActionRegistry) -> None:
        registry.contribute(
            _command("a", "&Start", shortcut="Ctrl+R", surface_id="bots")
        )
        registry.contribute(
            _command("b", "&Start", shortcut="Ctrl+R", surface_id="backtest")
        )

    def test_no_free_key_is_reserved_by_this_platform(self, qapp) -> None:
        """The free set drops every key KDE, GNOME or macOS reserves, so a
        consumer that boots on Windows boots here too."""
        assert _reserved_free_key() is None

    def test_a_key_the_platform_reserves_is_refused(
        self, owner: QWidget, confirmer: _AnsweringConfirmer, monkeypatch
    ) -> None:
        """Defence in depth: should a future Qt reserve a free key, the
        registry refuses it at boot rather than shadow a standard command."""
        monkeypatch.setattr(
            action_registry_module, "_standard_bindings", lambda: {"Ctrl+R": "FindNext"}
        )
        registry = ActionRegistry(owner, confirmer)
        with pytest.raises(ActionDeclarationError, match="reserves for FindNext"):
            registry.contribute(_command("b", "&Run", shortcut="Ctrl+R"))

    def test_two_items_of_one_menu_on_one_access_key(
        self, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("a", "&Start"))
        with pytest.raises(ActionDeclarationError, match="share an access key"):
            registry.contribute(_command("b", "&Stop"))

    def test_one_menu_spelled_with_two_access_keys(
        self, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("a", "&Start", menu_path=("T&rade",)))
        with pytest.raises(ActionDeclarationError, match="one menu has one access key"):
            registry.contribute(_command("b", "S&top", menu_path=("&Trade",)))


class TestTheBuiltAction:
    def test_it_is_disabled_until_bound(self, registry: ActionRegistry) -> None:
        action = registry.contribute(_command("a", "&Start"))
        assert not action.isEnabled()

        registry.bind("a", lambda checked: None)

        assert action.isEnabled()

    def test_its_tooltip_names_the_shortcut(self, registry: ActionRegistry) -> None:
        action = registry.contribute(_command("a", "&Start", shortcut="F9"))
        assert action.toolTip() == "Start (F9)"

    def test_a_bound_signal_enables_and_checks_it(
        self, registry: ActionRegistry
    ) -> None:
        presenter = _Presenter()
        action = registry.contribute(_command("a", "&Live trading", checkable=True))
        registry.bind(
            "a",
            lambda checked: None,
            enabled=presenter.can_start,
            checked=presenter.is_live,
        )

        presenter.can_start.emit(False)
        presenter.is_live.emit(True)

        assert not action.isEnabled()
        assert action.isChecked()

    def test_binding_twice_is_refused(self, registry: ActionRegistry) -> None:
        registry.contribute(_command("a", "&Start"))
        registry.bind("a", lambda checked: None)
        with pytest.raises(ActionDeclarationError, match="already bound"):
            registry.bind("a", lambda checked: None)


class TestRunning:
    def test_trigger_runs_the_handler(self, registry: ActionRegistry) -> None:
        ran: list[bool] = []
        action = registry.contribute(_command("a", "&Start"))
        registry.bind("a", ran.append)

        action.trigger()

        assert ran == [False]

    def test_a_rejected_confirmation_runs_nothing(
        self, registry: ActionRegistry, confirmer: _AnsweringConfirmer
    ) -> None:
        confirmer.answer = False
        ran: list[bool] = []
        action = registry.contribute(_command("a", "S&top", confirm=_STOP))
        registry.bind("a", ran.append)

        action.trigger()

        assert confirmer.asked == [_STOP]
        assert ran == []

    def test_an_accepted_confirmation_runs_the_handler(
        self, registry: ActionRegistry, confirmer: _AnsweringConfirmer
    ) -> None:
        ran: list[bool] = []
        action = registry.contribute(_command("a", "S&top", confirm=_STOP))
        registry.bind("a", ran.append)

        action.trigger()

        assert ran == [False]

    def test_a_rejected_checkable_command_keeps_its_state(
        self, registry: ActionRegistry, confirmer: _AnsweringConfirmer
    ) -> None:
        confirmer.answer = False
        heard: list[bool] = []
        action = registry.contribute(
            _command("a", "&Live trading", checkable=True, confirm=_STOP)
        )
        action.toggled.connect(heard.append)
        registry.bind("a", lambda checked: None)

        action.trigger()

        assert not action.isChecked()
        assert heard == [True, False], "a toggled listener must hear the way back"


class TestReading:
    def test_unbound_commands_are_reported(
        self, registry: ActionRegistry, caplog
    ) -> None:
        registry.contribute(_command("a", "&Start"))
        registry.contribute(_command("b", "S&top"))
        registry.bind("a", lambda checked: None)

        with caplog.at_level(logging.WARNING, logger="App"):
            assert registry.report_unbound() == ("b",)

        assert "have no handler" in caplog.text

    def test_a_menu_lists_global_and_its_mode_commands_only(
        self, registry: ActionRegistry
    ) -> None:
        stop = registry.contribute(_command("stop", "Emergency &stop", shortcut="F8"))
        bots = registry.contribute(_command("bots.start", "S&tart", surface_id="bots"))
        registry.contribute(_command("backtest.run", "&Run", surface_id="backtest"))

        assert registry.menu_actions(_TRADE, "bots") == (stop, bots)

    def test_a_toolbar_lists_its_actions(self, registry: ActionRegistry) -> None:
        start = registry.contribute(
            _command("a", "&Start", surface_id="bots", toolbar="header")
        )
        registry.contribute(_command("b", "S&top", surface_id="bots"))

        assert registry.toolbar_actions("bots", "header") == (start,)

    def test_menu_paths_in_first_contribution_order(
        self, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("a", "&Start", menu_path=("&Bots",)))
        registry.contribute(_command("b", "&Sync", menu_path=("&Data",)))
        registry.contribute(_command("c", "S&top", menu_path=("&Bots",)))

        assert registry.menu_paths() == (("&Bots",), ("&Data",))


class TestAccessKeysAcrossMenus:
    """Access keys are unique among siblings: menu-bar titles, and the items
    and submenus of one menu (`ui-architecture.md` §9.3)."""

    def test_one_menu_spelled_two_ways_by_two_modes(
        self, registry: ActionRegistry
    ) -> None:
        """Modes share the menu bar, so the spelling check ignores scope."""
        registry.contribute(
            _command("a", "&Start", menu_path=("T&rade",), surface_id="bots")
        )
        with pytest.raises(ActionDeclarationError, match="one menu has one access key"):
            registry.contribute(
                _command("b", "S&top", menu_path=("&Trade",), surface_id="backtest")
            )

    def test_two_menu_bar_titles_on_one_access_key(
        self, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("a", "&Start", menu_path=("&Trade",)))
        with pytest.raises(ActionDeclarationError, match="in the menu bar"):
            registry.contribute(_command("b", "&Options", menu_path=("&Tools",)))

    def test_an_item_and_a_submenu_on_one_access_key(
        self, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("a", "&Toolbars", menu_path=("&View",)))
        with pytest.raises(ActionDeclarationError, match="share an access key"):
            registry.contribute(_command("b", "&Close", menu_path=("&View", "&Tabs")))

    def test_distinct_keys_across_the_tree_are_accepted(
        self, registry: ActionRegistry
    ) -> None:
        registry.contribute(_command("a", "&Start", menu_path=("T&rade",)))
        registry.contribute(_command("b", "&Options", menu_path=("&Tools",)))
        registry.contribute(_command("c", "&Close", menu_path=("&View", "&Tabs")))
        registry.contribute(_command("d", "T&oolbars", menu_path=("&View",)))


class TestStartingDisabled:
    def test_it_can_stay_disabled_until_its_signal_fires(
        self, registry: ActionRegistry
    ) -> None:
        presenter = _Presenter()
        action = registry.contribute(_command("a", "&Start"))

        registry.bind(
            "a",
            lambda checked: None,
            enabled=presenter.can_start,
            initially_enabled=False,
        )
        assert not action.isEnabled()

        presenter.can_start.emit(True)
        assert action.isEnabled()
