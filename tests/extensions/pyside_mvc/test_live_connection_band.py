"""Tests for `LiveConnectionBand` (`EPIC-008A`) — the always-visible
connection status band `reference/handoff.md` §4 specifies.

Uses a standalone `QQmlEngine` with its own directly-injected `Theme`
context property, NOT `configure_app_qml()`/`get_theme_bridge()` (the
pattern every other kit test in this directory uses). That singleton is
first-call-wins for the whole pytest process, and every existing fixture
locks it to an all-`#000000` placeholder palette (`test_widget_kit_gallery
.py::_PLACEHOLDER_PALETTE`) -- fine for "does this render", useless for
"does state X map to colour Y", since every candidate colour would be
identical black. A distinguishable palette here, isolated from the shared
singleton, is the only way to actually prove the tier-1 state->colour
mapping (`ui-architecture.md` §1.2's own "should a button know a
background task is running? It knows busy" logic, applied to a connection
state instead of a boolean) is wired to the right token per state.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMetaObject, QObject, Qt, Slot
from PySide6.QtGui import QColor

from tests.extensions.pyside_mvc._standalone_qml_theme import (
    load_qml_fixture,
    standalone_theme_engine,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _standalone_theme_engine():
    return standalone_theme_engine()


def _load_band(engine):
    return load_qml_fixture(engine, _FIXTURES_DIR / "live_connection_band_probe.qml")


class _Recorder(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.action_count = 0

    @Slot()
    def on_action(self) -> None:
        self.action_count += 1


def test_state_maps_to_the_correct_theme_colour_for_every_state(qtbot):
    """`reference/handoff.md` §4's own table: accent in READING;
    accent-700 in IDLE/CONNECTING; fault (danger) in FAILED/STALE/COLD."""
    engine, theme, merged = _standalone_theme_engine()
    band = _load_band(engine)
    qtbot.wait(1)

    expected_token_by_state = {
        "reading": "accent",
        "idle": "accent700",
        "connecting": "accent700",
        "failed": "danger",
        "stale": "danger",
        "cold": "danger",
    }

    stripe = band.findChild(QObject, "connectionStateStripe")
    dot = band.findChild(QObject, "connectionStateDot")
    assert stripe is not None
    assert dot is not None

    for state, token in expected_token_by_state.items():
        band.setProperty("state", state)
        expected = QColor(merged[token])
        assert QColor(stripe.property("color")) == expected, state
        assert QColor(dot.property("color")) == expected, state


def test_an_unrecognized_state_falls_back_to_muted_rather_than_a_wrong_colour(qtbot):
    engine, theme, merged = _standalone_theme_engine()
    band = _load_band(engine)
    qtbot.wait(1)

    band.setProperty("state", "some-typo-state")

    dot = band.findChild(QObject, "connectionStateDot")
    assert QColor(dot.property("color")) == QColor(merged["muted"])


def test_action_button_click_emits_action_requested(qtbot):
    engine, theme, merged = _standalone_theme_engine()
    band = _load_band(engine)
    qtbot.wait(1)
    recorder = _Recorder()
    band.actionRequested.connect(recorder.on_action)

    button = band.findChild(QObject, "connectionActionButton")
    assert button is not None
    assert QMetaObject.invokeMethod(button, "clicked")

    assert recorder.action_count == 1


def test_change_target_link_has_a_clickable_area(qtbot):
    engine, theme, merged = _standalone_theme_engine()
    band = _load_band(engine)
    qtbot.wait(1)

    area = band.findChild(QObject, "connectionChangeTargetArea")
    assert area is not None
    assert area.property("cursorShape") == Qt.PointingHandCursor


def test_change_target_click_emits_change_target_requested(qtbot):
    """Via `_requestChangeTarget()` — invokable with no argument from
    Python the way `MouseArea.clicked(mouse)` cannot be (that needs a real
    `QQuickMouseEvent`; `Button.clicked()`, used for the action button
    above, happens to be the one QtQuick signal that is zero-arg). Added
    retroactively, matching the pattern `AppRail._selectRow(id)` used from
    the start — this component predates that discovery, so its own
    `onClicked` binding shipped tested only by inspection until now."""
    engine, theme, merged = _standalone_theme_engine()
    band = _load_band(engine)
    qtbot.wait(1)
    recorder = _Recorder()
    band.changeTargetRequested.connect(recorder.on_action)

    assert QMetaObject.invokeMethod(band, "_requestChangeTarget")

    assert recorder.action_count == 1


def _heartbeat_ticks(ribbon):
    """@brief Only the delegate items, not the `Repeater` itself — a
    `Repeater` is a non-visual `QQuickItem` that still shows up as one of
    its parent's `childItems()` (a real, zero-size, id-less entry
    confirmed by inspection), which would otherwise silently inflate any
    count-based assertion by one."""
    return [
        child for child in ribbon.childItems() if child.objectName() == "heartbeatTick"
    ]


def test_heartbeat_ribbon_renders_one_tick_per_sample(qtbot):
    engine, theme, merged = _standalone_theme_engine()
    band = _load_band(engine)
    qtbot.wait(1)

    ribbon = band.findChild(QObject, "heartbeatRibbon")
    assert ribbon is not None
    # The fixture's own heartbeatTicks: [0.2, 0.6, 1.0].
    assert len(_heartbeat_ticks(ribbon)) == 3


def test_heartbeat_ribbon_newest_tick_is_full_opacity_older_ticks_fade(qtbot):
    engine, theme, merged = _standalone_theme_engine()
    band = _load_band(engine)
    qtbot.wait(1)

    ribbon = band.findChild(QObject, "heartbeatRibbon")
    ticks = _heartbeat_ticks(ribbon)
    assert [round(t.property("opacity"), 2) for t in ticks] == [0.35, 0.35, 1.0]


def test_heartbeat_ribbon_is_empty_when_no_ticks_supplied(qtbot):
    engine, theme, merged = _standalone_theme_engine()
    band = _load_band(engine)
    qtbot.wait(1)

    band.setProperty("heartbeatTicks", [])

    ribbon = band.findChild(QObject, "heartbeatRibbon")
    assert _heartbeat_ticks(ribbon) == []


def test_action_and_state_text_pass_through_verbatim(qtbot):
    engine, theme, merged = _standalone_theme_engine()
    band = _load_band(engine)
    qtbot.wait(1)

    label = band.findChild(QObject, "connectionStateLabel")
    note = band.findChild(QObject, "connectionStateNote")
    target = band.findChild(QObject, "connectionTargetText")

    assert label.property("text") == "Attached · reading"
    assert note.property("text") == "snapshot stream live · ~1/s"
    assert target.property("text") == "ws://127.0.0.1:8781"
