"""Sanity coverage for the Widget Kit (EPIC-001C): the Gallery loads clean,
AppDataTable wires columns/model end to end, and the kit's own QML source
carries zero literal colour values — dogfooding the guard EPIC-001B shipped
on the exact surface ui-architecture.md §2.2 targets."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QIcon

from sagittarius_engine.extensions.pyside_mvc.runtime import (
    configure_app_qml,
    create_quick_widget,
)
from sagittarius_engine.extensions.pyside_mvc.tokens import (
    REQUIRED_COLOUR_TOKEN_NAMES,
    find_literal_colors,
)

_PYSIDE_MVC_DIR = (
    Path(__file__).resolve().parents[3]
    / "sagittarius_engine"
    / "extensions"
    / "pyside_mvc"
)
#: The widget kit's real QML home — one directory per component — after the
#: EPIC-001C directory-per-component reorg (2026-08-23).
_QML_KIT_DIR = _PYSIDE_MVC_DIR / "Sagittarius" / "UI"
#: The kit's QML surface spans two directories: the widget kit proper
#: (`Sagittarius/UI/`) and the runtime's own `OverlayHost.qml` (`runtime/`,
#: paired with `overlay_host.py` since it's bootstrap plumbing, not a
#: reusable kit component). Scanning the whole extension root — not just
#: the kit directory — keeps the anti-literal-colour guard covering both
#: without hardcoding a second path here. Computed independently of
#: `_QML_KIT_DIR` (not via `.parent`) since the kit now nests two levels
#: deep (`Sagittarius/UI/`) rather than one.
_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_PLACEHOLDER_PALETTE = {name: "#000000" for name in REQUIRED_COLOUR_TOKEN_NAMES}


class _TestIconLoader:
    def get_icon(self, name: str, color: str, size: int) -> QIcon:
        return QIcon()


@pytest.fixture(scope="module", autouse=True)
def configure_qml() -> None:
    configure_app_qml(_PLACEHOLDER_PALETTE, _TestIconLoader(), {})


def test_gallery_loads_with_no_qml_errors(qtbot):
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(QUrl.fromLocalFile(str(_QML_KIT_DIR / "Gallery" / "Gallery.qml")))

    assert widget.errors() == []
    assert widget.rootObject() is not None


def test_app_data_table_renders_every_row_from_its_model(qtbot):
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(
        QUrl.fromLocalFile(str(_FIXTURES_DIR / "app_data_table_probe.qml"))
    )

    assert widget.errors() == []
    root = widget.rootObject()
    assert root is not None

    rows_view = root.findChild(QObject, "appDataTableRows")
    assert rows_view is not None
    assert rows_view.property("count") == 2


def test_app_modal_opens_dynamically_sized_with_its_action_buttons(qtbot):
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(QUrl.fromLocalFile(str(_FIXTURES_DIR / "app_modal_probe.qml")))

    assert widget.errors() == []
    root = widget.rootObject()
    assert root is not None

    modal = root.findChild(QObject, "probeModal")
    assert modal is not None
    assert modal.property("opened") is True
    assert modal.property("title") == "Probe Modal"
    # Dynamic sizing (qml-rule.md §2.2): width must never exceed the
    # component's own declared cap, never a bare fixed number asserted here.
    assert modal.property("width") <= modal.property("maxWidth")

    assert root.findChild(QObject, "btnCancel") is not None
    assert root.findChild(QObject, "btnConfirm") is not None


def test_widget_kit_source_has_zero_literal_colours():
    """The permanent regression test: this exact check already caught 8
    real pre-existing violations in QmlShared when first run (2026-08-22) —
    two legitimate Theme-unavailable fallbacks (now marked token-exempt),
    three with no matching semantic token yet (marked token-exempt with a
    reason), and three genuine drift bugs (fixed to use the matching
    existing token). This test is what keeps the kit at zero going
    forward."""
    findings = find_literal_colors(_PYSIDE_MVC_DIR)

    assert findings == []
