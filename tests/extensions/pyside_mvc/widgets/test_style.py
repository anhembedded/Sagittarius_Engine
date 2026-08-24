"""Tests for `widgets.style.apply_role()` — the composition point that
replaces a shared styling base class (see EPIC-006's architecture ADR §3
for why no such base exists)."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame

from sagittarius_engine.extensions.pyside_mvc.tokens import get_theme_bridge
from sagittarius_engine.extensions.pyside_mvc.widgets import (
    StyleRole,
    WidgetState,
    apply_role,
)


def test_apply_role_sets_a_non_empty_stylesheet(qtbot):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.SURFACE)

    assert widget.styleSheet() != ""


def test_surface_role_uses_the_live_bgcard_token(qtbot):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.SURFACE)

    live_bg_card = str(get_theme_bridge().value("bgCard"))
    assert live_bg_card in widget.styleSheet()


def test_field_role_uses_the_live_border_token(qtbot):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.FIELD)

    live_border = str(get_theme_bridge().value("border"))
    assert live_border in widget.styleSheet()


def test_disabled_state_produces_different_qss_than_normal_for_buttons(
    qtbot, fake_theme_bridge
):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.PRIMARY_BUTTON, state=WidgetState.NORMAL)
    normal_qss = widget.styleSheet()

    apply_role(widget, StyleRole.PRIMARY_BUTTON, state=WidgetState.DISABLED)
    disabled_qss = widget.styleSheet()

    assert normal_qss != disabled_qss


def test_disabled_button_uses_the_live_muted_token(qtbot):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.DANGER_BUTTON, state=WidgetState.DISABLED)

    live_muted = str(get_theme_bridge().value("muted"))
    assert live_muted in widget.styleSheet()


def test_checkbox_and_field_roles_ignore_disabled_state():
    """These two roles' QSS blocks have no disabled-state branch (see
    style._build_qss) — asserting that explicitly, so a future change
    that silently drops disabled handling for buttons doesn't also
    silently claim these roles handle it when they never did."""
    from PySide6.QtWidgets import QWidget

    checkbox_widget = QWidget()
    field_widget = QWidget()

    apply_role(checkbox_widget, StyleRole.CHECKBOX, state=WidgetState.NORMAL)
    normal_checkbox_qss = checkbox_widget.styleSheet()
    apply_role(checkbox_widget, StyleRole.CHECKBOX, state=WidgetState.DISABLED)
    assert checkbox_widget.styleSheet() == normal_checkbox_qss

    apply_role(field_widget, StyleRole.FIELD, state=WidgetState.NORMAL)
    normal_field_qss = field_widget.styleSheet()
    apply_role(field_widget, StyleRole.FIELD, state=WidgetState.DISABLED)
    assert field_widget.styleSheet() == normal_field_qss
