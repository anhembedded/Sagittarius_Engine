"""`runtime/quick_background.py` + the clear colour `create_quick_widget()`
now sets — TASK-042.

Why this exists as a mechanism test and not a screenshot: the defect it
guards against is invisible on the software rendering path every headless
test uses (`offscreen`, `widget.grab()`), and only shows on the texture path
of a real desktop session — see the module docstring of `quick_background`.
A headless test therefore cannot see the *symptom*; it can only pin the
*contract* whose violation produces it: the clear colour is opaque and is
the named token. The reference consumer's `BUG-115` carries the on-screen
evidence (Xvfb + xcb pixel samples).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor

from sagittarius_engine.extensions.pyside_mvc.runtime import (
    DEFAULT_BACKGROUND,
    configure_app_qml,
    create_quick_widget,
    resolve_opaque_background,
)
from sagittarius_engine.extensions.pyside_mvc.tokens import (
    REQUIRED_COLOUR_TOKEN_NAMES,
    get_theme_bridge,
)

_PLACEHOLDER_PALETTE = dict.fromkeys(REQUIRED_COLOUR_TOKEN_NAMES, "#000000")
_OPAQUE_ALPHA = 255


class _NoIcons:
    def get_icon(self, name: str, color: str, size: int):  # pragma: no cover
        raise AssertionError("no icon is requested by these tests")


@pytest.fixture(scope="module", autouse=True)
def _configured() -> None:
    # `get_theme_bridge()` is first-caller-wins for the whole session, so
    # every assertion below reads the *live* bridge value instead of
    # assuming this placeholder won the race.
    configure_app_qml(_PLACEHOLDER_PALETTE, _NoIcons(), {})
    get_theme_bridge(_PLACEHOLDER_PALETTE)


def _live(token: str) -> QColor:
    return QColor(str(get_theme_bridge().value(token)))


def test_default_token_is_the_app_background():
    assert DEFAULT_BACKGROUND == "bg"
    assert "bg" in REQUIRED_COLOUR_TOKEN_NAMES


def test_resolves_a_required_colour_token_to_an_opaque_colour():
    colour = resolve_opaque_background("bgCard")
    assert colour.isValid()
    assert colour.alpha() == _OPAQUE_ALPHA
    assert colour.rgb() == _live("bgCard").rgb()


def test_unknown_token_is_a_named_failure_not_an_invalid_colour():
    with pytest.raises(KeyError, match="noSuchToken"):
        resolve_opaque_background("noSuchToken")


def test_translucent_token_is_refused():
    # A private token name so the shared bridge is not left holding a
    # translucent value under a name another test might read.
    get_theme_bridge().insert("_task042Translucent", "#80ff0000")
    with pytest.raises(ValueError, match="not opaque"):
        resolve_opaque_background("_task042Translucent")


def test_non_colour_token_is_refused():
    get_theme_bridge().insert("_task042NotAColour", "not a colour")
    with pytest.raises(ValueError, match="not a colour"):
        resolve_opaque_background("_task042NotAColour")


def test_create_quick_widget_clears_to_the_default_token(qtbot):
    widget = create_quick_widget()
    qtbot.addWidget(widget)
    # `QQuickWidget.clearColor()` is not bound in PySide6; the offscreen
    # QQuickWindow's `color` is the value `setClearColor()` writes.
    colour = widget.quickWindow().color()
    assert colour.alpha() == _OPAQUE_ALPHA
    assert colour.rgb() == _live(DEFAULT_BACKGROUND).rgb()


def test_create_quick_widget_clears_to_the_requested_token(qtbot):
    get_theme_bridge().insert("_task042Card", "#123456")
    widget = create_quick_widget(background="_task042Card")
    qtbot.addWidget(widget)
    assert widget.quickWindow().color().name() == "#123456"


def test_create_quick_widget_refuses_a_translucent_token(qtbot):
    get_theme_bridge().insert("_task042Glass", "#40000000")
    with pytest.raises(ValueError, match="not opaque"):
        create_quick_widget(background="_task042Glass")
