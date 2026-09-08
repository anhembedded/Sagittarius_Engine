"""`EPIC-007E` criterion 4: `tokens.qml_literal_guard` and
`kit.raw_primitive_guard` both pass over `tools/state_console/`, in the
shape `tests/extensions/pyside_mvc/test_widget_kit_gallery.py` already
proves them against the kit's own real tree."""

from __future__ import annotations

from pathlib import Path

from sagittarius_engine.extensions.pyside_mvc.kit.raw_primitive_guard import (
    find_raw_primitives,
)
from sagittarius_engine.extensions.pyside_mvc.tokens.qml_literal_guard import (
    find_literal_colors,
)

_STATE_CONSOLE_DIR = Path(__file__).resolve().parents[3] / "tools" / "state_console"


def test_no_literal_colours_in_state_console_qml():
    findings = find_literal_colors(_STATE_CONSOLE_DIR)
    assert findings == [], findings


def test_no_raw_primitives_in_state_console_qml():
    findings = find_raw_primitives(_STATE_CONSOLE_DIR)
    assert findings == [], findings
