"""Tests for `widgets.surfaces.banner.Banner`."""

from __future__ import annotations

import pytest

from sagittarius_engine.extensions.pyside_mvc.widgets import (
    Banner,
    Panel,
    Severity,
    StyleRole,
)


def test_is_a_panel(qtbot):
    banner = Banner("Đồ thị xem trước")
    qtbot.addWidget(banner)

    assert isinstance(banner, Panel)
    assert banner.message == "Đồ thị xem trước"
    assert banner.severity is Severity.INFO


def test_icon_and_action_are_hidden_unless_given(qtbot):
    banner = Banner("plain")
    qtbot.addWidget(banner)

    assert banner.icon_label.isVisibleTo(banner) is False
    assert banner.action_button.isVisibleTo(banner) is False


def test_icon_and_action_appear_when_given(qtbot):
    banner = Banner("stale", icon="⚠️", action_text="Chạy lại ngay")
    qtbot.addWidget(banner)

    assert banner.icon == "⚠️"
    assert banner.icon_label.isVisibleTo(banner) is True
    assert banner.action_button.text() == "Chạy lại ngay"
    assert banner.action_button.isVisibleTo(banner) is True


def test_each_severity_renders_differently(qtbot, fake_theme_bridge):
    rendered = {}
    for severity in (Severity.INFO, Severity.WARN, Severity.DANGER):
        banner = Banner("x", severity=severity)
        qtbot.addWidget(banner)
        rendered[severity] = banner.styleSheet()

    assert len(set(rendered.values())) == 3
    assert "<accent>" in rendered[Severity.INFO]
    assert "<warning>" in rendered[Severity.WARN]
    assert "<danger>" in rendered[Severity.DANGER]


def test_severity_is_switchable_after_construction(qtbot, fake_theme_bridge):
    """The consumer's audit banner recolours between pass and fail on every
    sync — the one behaviour its four static backtest banners do not need."""
    banner = Banner("Kiểm định", severity=Severity.DANGER)
    qtbot.addWidget(banner)
    before = banner.styleSheet()

    banner.set_severity(Severity.INFO)

    assert banner.severity is Severity.INFO
    assert banner.styleSheet() != before


def test_a_non_severity_role_is_rejected(qtbot):
    with pytest.raises(ValueError, match="Banner severity must be one of"):
        Banner("x", severity=StyleRole.PRIMARY_BUTTON)


def test_set_severity_also_rejects_a_non_severity_role(qtbot):
    banner = Banner("x")
    qtbot.addWidget(banner)

    with pytest.raises(ValueError, match="Banner severity must be one of"):
        banner.set_severity(StyleRole.SURFACE)


def test_action_text_can_be_relabelled_mid_flight(qtbot):
    """The consumer's cancel action flips between "Hủy" and "Đang hủy..."
    while the operation runs."""
    banner = Banner("Đang chạy", action_text="Hủy")
    qtbot.addWidget(banner)

    banner.set_action_text("Đang hủy...")
    assert banner.action_button.text() == "Đang hủy..."

    banner.set_action_text("")
    assert banner.action_button.isVisibleTo(banner) is False


def test_message_and_icon_are_settable(qtbot):
    banner = Banner("first")
    qtbot.addWidget(banner)

    banner.message = "second"
    banner.icon = "✅"

    assert banner.message == "second"
    assert banner.icon_label.isVisibleTo(banner) is True
