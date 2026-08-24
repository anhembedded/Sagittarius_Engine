"""Tests for `BaseQmlViewModel` — the FSM-driven `uiMode`/`controlsEnabled`
base every QML (and, since EPIC-006D, QtWidgets) screen ViewModel shares."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel


class _LockableViewModel(BaseQmlViewModel):
    DISABLED_UI_MODES = frozenset({"LOCKED", "LIVE"})


@pytest.fixture
def vm(qapp):
    return _LockableViewModel()


def test_initial_state_is_idle_and_controls_enabled(vm):
    assert vm.uiMode == "IDLE"
    assert vm.controlsEnabled is True


def test_set_ui_mode_updates_both_properties(vm):
    vm.set_ui_mode("LOCKED")

    assert vm.uiMode == "LOCKED"
    assert vm.controlsEnabled is False


def test_set_ui_mode_to_the_same_value_is_a_no_op(vm):
    changes = []
    vm.uiModeChanged.connect(lambda: changes.append(vm.uiMode))

    vm.set_ui_mode("IDLE")  # already IDLE

    assert changes == []


def test_controls_enabled_changed_only_fires_when_the_derived_value_flips(vm):
    fired = []
    vm.controlsEnabledChanged.connect(lambda: fired.append(vm.controlsEnabled))

    vm.set_ui_mode("LOCKED")  # True -> False, fires
    vm.set_ui_mode("LIVE")  # False -> False (still disabled), no fire

    assert fired == [False]


def test_controls_enabled_is_already_correct_inside_a_ui_mode_changed_listener(vm):
    """
    Regression test (EPIC-006D / bug found building the first QtWidgets
    consumer of `controlsEnabled`): a direct (same-thread) Qt connection
    runs its slot synchronously inside `.emit()`. A slot connected to
    `uiModeChanged` that reads `vm.controlsEnabled` must see the
    already-updated value -- not a stale one from before this
    `set_ui_mode()` call. QML's declarative bindings never had a way to
    observe this ordering bug (a binding re-evaluates lazily, after
    `set_ui_mode()` has already returned and both signals have fired), so
    it went undetected until an imperative QtWidgets consumer connected
    directly.
    """
    observed_during_ui_mode_changed: list[bool] = []
    vm.uiModeChanged.connect(
        lambda: observed_during_ui_mode_changed.append(vm.controlsEnabled)
    )

    vm.set_ui_mode("LIVE")

    assert observed_during_ui_mode_changed == [False]


def test_controls_enabled_is_already_correct_even_when_it_does_not_change(vm):
    """Same guarantee, for a transition where controlsEnabled's own value
    does not flip (LOCKED -> LIVE, both disabled) -- uiModeChanged still
    fires (uiMode itself changed), and controlsEnabled must already read
    correctly even though controlsEnabledChanged does not fire this time."""
    vm.set_ui_mode("LOCKED")

    observed: list[bool] = []
    vm.uiModeChanged.connect(lambda: observed.append(vm.controlsEnabled))

    vm.set_ui_mode("LIVE")

    assert observed == [False]


def test_a_subclass_with_no_disabled_modes_keeps_controls_always_enabled(qapp):
    class _AlwaysEnabled(BaseQmlViewModel):
        pass

    vm = _AlwaysEnabled()
    vm.set_ui_mode("ANYTHING")

    assert vm.controlsEnabled is True
