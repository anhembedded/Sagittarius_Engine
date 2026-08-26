"""A `BaseView` must paint the background its stylesheet asks for.

Written from a user-reported symptom, not from reading the class: a
sidebar that had asked for its own darker background since the day it was
written, and never got it.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from sagittarius_engine.extensions.pyside_mvc import BaseView

_BACKGROUND = "#0d0e11"


class _Sidebar(BaseView):
    pass


def test_a_nested_view_paints_its_stylesheet_background(qtbot):
    """The case that was broken. A plain `QWidget` subclass ignores a
    stylesheet background once it is nested inside another widget.

    Standalone it paints — which is why nothing caught this. A view under
    test is the top-level window and Qt fills that itself; only in a real
    window, inside a layout, does the rule go quiet.
    """
    host = QWidget()
    qtbot.addWidget(host)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)

    sidebar = _Sidebar()
    sidebar.setStyleSheet(f"_Sidebar {{ background-color: {_BACKGROUND}; }}")
    layout.addWidget(sidebar)
    host.resize(200, 120)
    host.show()

    painted = host.grab().toImage().pixelColor(100, 60).name()

    assert painted == _BACKGROUND


def test_the_attribute_is_what_makes_that_work(qtbot):
    """Pinned separately from the pixel: the pixel test would also pass if
    some later change made Qt fill the widget for an unrelated reason, and
    then quietly stop covering the thing it was written for."""
    sidebar = _Sidebar()
    qtbot.addWidget(sidebar)

    assert sidebar.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)


def test_a_view_with_no_stylesheet_of_its_own_adds_nothing(qtbot):
    """The attribute must not hand every view a background it never asked
    for — with no rule naming it, there is nothing to paint."""
    host = QWidget()
    qtbot.addWidget(host)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    host.setStyleSheet("QWidget { background-color: #123456; }")

    layout.addWidget(_Sidebar())
    host.resize(200, 120)
    host.show()

    assert host.grab().toImage().pixelColor(100, 60).name() == "#123456"
