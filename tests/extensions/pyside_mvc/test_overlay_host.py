"""Behavior tests for the full-window QML overlay host (BOT-087)."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QWidget

from sagittarius_engine.extensions.pyside_mvc.runtime import (
    OverlayHost,
    configure_app_qml,
)
from sagittarius_engine.extensions.pyside_mvc.tokens import REQUIRED_COLOUR_TOKEN_NAMES

_PROBE_QML = Path(__file__).parent / "fixtures" / "overlay_host_probe.qml"
#: This suite doesn't exercise theming — arbitrary placeholder values that
#: satisfy configure_app_qml()'s required-token validation (EPIC-001B), not
#: real visual constants.
_PLACEHOLDER_PALETTE = dict.fromkeys(REQUIRED_COLOUR_TOKEN_NAMES, "#000000")
_INITIAL_WIDTH = 640
_INITIAL_HEIGHT = 480
_RESIZED_WIDTH = 1000
_RESIZED_HEIGHT = 600
_CONTEXT_LABEL = "Backtest overlay"
_MODAL_COLOR = QColor("#1A365D")


class _TestIconLoader:
    """Satisfies shared QML setup; the overlay probe does not render icons."""

    def get_icon(self, name: str, color: str, size: int) -> QIcon:
        return QIcon()


@pytest.fixture(scope="module", autouse=True)
def configure_qml() -> None:
    configure_app_qml(_PLACEHOLDER_PALETTE, _TestIconLoader(), {})


@pytest.fixture
def parent_widget(qtbot) -> QWidget:
    widget = QWidget()
    widget.resize(_INITIAL_WIDTH, _INITIAL_HEIGHT)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def _load_probe(host: OverlayHost) -> None:
    host.load_content(
        QUrl.fromLocalFile(str(_PROBE_QML)), {"overlayLabel": _CONTEXT_LABEL}
    )


def test_overlay_matches_parent_and_exposes_qml_overlay_dimensions(
    qtbot, parent_widget: QWidget
) -> None:
    host = OverlayHost(parent_widget)
    _load_probe(host)

    qtbot.waitUntil(lambda: host.content_item is not None)
    content_item = host.content_item
    assert content_item is not None

    assert host.quick_widget.geometry() == parent_widget.rect()
    assert host.overlay_size == (_INITIAL_WIDTH, _INITIAL_HEIGHT)
    assert content_item.property("suppliedLabel") == _CONTEXT_LABEL

    parent_widget.resize(_RESIZED_WIDTH, _RESIZED_HEIGHT)
    qtbot.waitUntil(lambda: host.overlay_size == (_RESIZED_WIDTH, _RESIZED_HEIGHT))

    assert host.quick_widget.geometry() == parent_widget.rect()


def test_qml_modal_state_controls_click_through_without_python_state(
    qtbot, parent_widget: QWidget
) -> None:
    host = OverlayHost(parent_widget)
    _load_probe(host)

    qtbot.waitUntil(lambda: host.content_item is not None)
    content_item = host.content_item
    assert content_item is not None
    assert host.is_click_through is True

    content_item.setProperty("hasOpenModal", True)
    qtbot.waitUntil(lambda: host.is_click_through is False)

    content_item.setProperty("hasOpenModal", False)
    qtbot.waitUntil(lambda: host.is_click_through is True)


def test_open_modal_visually_overlays_the_parent_widget(
    qtbot, parent_widget: QWidget
) -> None:
    """A real QML Popup must paint over QWidget content, the same boundary
    used by BackTestView's native ChartCard.  This catches a false-positive
    ``raise_()`` implementation that reports the right geometry but is still
    hidden below a native widget."""
    parent_widget.setStyleSheet("background: #B91C1C;")
    host = OverlayHost(parent_widget)
    _load_probe(host)

    qtbot.waitUntil(lambda: host.content_item is not None)
    content_item = host.content_item
    assert content_item is not None
    content_item.setProperty("hasOpenModal", True)

    center = parent_widget.rect().center()

    def modal_is_visible_above_parent_content() -> bool:
        image = parent_widget.grab().toImage()
        return image.pixelColor(center) == _MODAL_COLOR

    qtbot.waitUntil(modal_is_visible_above_parent_content)


def test_clearing_content_restores_click_through(parent_widget: QWidget, qtbot) -> None:
    host = OverlayHost(parent_widget)
    _load_probe(host)
    qtbot.waitUntil(lambda: host.content_item is not None)
    content_item = host.content_item
    assert content_item is not None
    content_item.setProperty("hasOpenModal", True)
    qtbot.waitUntil(lambda: host.is_click_through is False)

    host.clear_content()
    qtbot.waitUntil(lambda: host.content_item is None)

    assert host.is_click_through is True


def test_loading_an_empty_url_fails_fast(parent_widget: QWidget) -> None:
    host = OverlayHost(parent_widget)

    with pytest.raises(ValueError, match="valid QUrl"):
        host.load_content(QUrl())


def test_dispose_is_idempotent(parent_widget: QWidget) -> None:
    host = OverlayHost(parent_widget)

    host.dispose()
    host.dispose()

    assert host.quick_widget.parentWidget() is parent_widget
