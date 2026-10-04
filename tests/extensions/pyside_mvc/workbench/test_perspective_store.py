"""A mode's layout survives a restart, and a stale one never half-applies
(`EPIC-008B`)."""

from __future__ import annotations

import logging

import pytest
from PySide6.QtWidgets import QLabel

from sagittarius_engine.extensions.pyside_mvc import (
    PerspectiveStore,
    RegionHost,
    RegionKind,
    SurfaceDeclaration,
    perspective_key,
)
from sagittarius_engine.extensions.ui_state import IStateContributor

_REGIONS = {"rail": RegionKind.DOCK_RIGHT, "console": RegionKind.DOCK_BOTTOM}


def _host(qtbot, *, layout_version: int = 1) -> RegionHost:
    """A mode built the same way every run, as a real boot builds it."""
    host = RegionHost(
        SurfaceDeclaration(surface_id="bots", accepts=frozenset(_REGIONS)),
        _REGIONS,
        layout_version=layout_version,
    )
    qtbot.addWidget(host)
    host.place_widget("rail", QLabel("bots"), title="Bots")
    host.place_widget("console", QLabel("log"), title="Log")
    host.show()
    host.capture_default_perspective()
    return host


def _log_toggle(host: RegionHost):
    return next(a for a in host.dock_toggle_actions() if a.text() == "Log")


def test_it_is_a_state_contributor() -> None:
    assert isinstance(PerspectiveStore(), IStateContributor)


def test_a_closed_panel_stays_closed_after_a_restart(qtbot) -> None:
    first_run = _host(qtbot)
    store = PerspectiveStore()
    store.register(first_run)
    _log_toggle(first_run).trigger()
    saved = store.capture_state()

    second_run = _host(qtbot)
    restarted = PerspectiveStore()
    restarted.register(second_run)
    restarted.restore_state(saved)

    assert not _log_toggle(second_run).isChecked()


def test_a_layout_of_another_version_restores_the_default(qtbot, caplog) -> None:
    first_run = _host(qtbot, layout_version=1)
    store = PerspectiveStore()
    store.register(first_run)
    _log_toggle(first_run).trigger()
    saved = store.capture_state()

    second_run = _host(qtbot, layout_version=2)
    _log_toggle(second_run).trigger()
    restarted = PerspectiveStore()
    restarted.register(second_run)
    with caplog.at_level(logging.INFO, logger="App"):
        restarted.restore_state(saved)

    assert _log_toggle(second_run).isChecked()
    assert caplog.text.count("opened with its default layout") == 1


def test_an_unreadable_entry_restores_the_default(qtbot) -> None:
    host = _host(qtbot)
    _log_toggle(host).trigger()
    store = PerspectiveStore()
    store.register(host)

    store.restore_state({perspective_key("bots"): {"version": 1, "state": "%%%"}})

    assert _log_toggle(host).isChecked()


def test_no_entry_leaves_the_layout_alone(qtbot) -> None:
    host = _host(qtbot)
    _log_toggle(host).trigger()
    store = PerspectiveStore()
    store.register(host)

    store.restore_state({})

    assert not _log_toggle(host).isChecked()


def test_two_hosts_for_one_surface_are_refused(qtbot) -> None:
    store = PerspectiveStore()
    store.register(_host(qtbot))
    with pytest.raises(ValueError, match="already registered"):
        store.register(_host(qtbot))
