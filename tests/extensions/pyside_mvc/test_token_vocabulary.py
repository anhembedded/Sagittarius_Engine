"""Tests for the design-token layer (EPIC-001B): the fixed required-colour
vocabulary, bootstrap-time completeness validation, and the merge that
backs every default-supplied token category."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QIcon

from sagittarius_engine.extensions.pyside_mvc.runtime.qml_host_view import (
    configure_app_qml,
)
from sagittarius_engine.extensions.pyside_mvc.tokens import (
    DEFAULT_MOTION_TOKENS,
    DEFAULT_RADIUS_TOKENS,
    DEFAULT_SPACING_TOKENS,
    DEFAULT_STATE_TOKENS,
    DEFAULT_TYPOGRAPHY_TOKENS,
    REQUIRED_COLOUR_TOKEN_NAMES,
    MissingRequiredTokensError,
    missing_required_tokens,
    with_token_defaults,
)

_COMPLETE_PALETTE = dict.fromkeys(REQUIRED_COLOUR_TOKEN_NAMES, "#000000")


class _TestIconLoader:
    def get_icon(self, name: str, color: str, size: int) -> QIcon:
        return QIcon()


# --- missing_required_tokens() -----------------------------------------


def test_missing_required_tokens_reports_nothing_for_a_complete_palette():
    assert missing_required_tokens(_COMPLETE_PALETTE) == []


def test_missing_required_tokens_reports_every_absent_required_key():
    partial = {"accent": "#F3BA2F", "bg": "#0a0a0c"}

    missing = missing_required_tokens(partial)

    assert set(missing) == REQUIRED_COLOUR_TOKEN_NAMES - {"accent", "bg"}


def test_missing_required_tokens_reports_all_when_palette_is_empty():
    assert set(missing_required_tokens({})) == REQUIRED_COLOUR_TOKEN_NAMES


def test_missing_required_tokens_ignores_extra_app_specific_keys():
    """An app may supply keys beyond the required vocabulary (e.g. its own
    icon-related colours) — completeness is about required keys being
    present, not about the palette being an exact-match set."""
    palette = {**_COMPLETE_PALETTE, "somethingAppSpecific": "#abc123"}

    assert missing_required_tokens(palette) == []


# --- configure_app_qml() bootstrap validation ---------------------------


def test_configure_app_qml_raises_on_incomplete_palette():
    incomplete = {"accent": "#F3BA2F"}

    with pytest.raises(MissingRequiredTokensError) as exc_info:
        configure_app_qml(incomplete, _TestIconLoader(), {})

    missing = set(exc_info.value.missing)
    assert missing == REQUIRED_COLOUR_TOKEN_NAMES - {"accent"}


def test_configure_app_qml_error_message_names_every_missing_token():
    with pytest.raises(MissingRequiredTokensError) as exc_info:
        configure_app_qml({}, _TestIconLoader(), {})

    message = str(exc_info.value)
    for name in REQUIRED_COLOUR_TOKEN_NAMES:
        assert name in message


def test_configure_app_qml_accepts_a_complete_palette():
    # Must not raise.
    configure_app_qml(_COMPLETE_PALETTE, _TestIconLoader(), {})


# --- with_token_defaults() merge ----------------------------------------


def test_with_token_defaults_exposes_every_default_backed_category():
    merged = with_token_defaults(_COMPLETE_PALETTE)

    for defaults in (
        DEFAULT_SPACING_TOKENS,
        DEFAULT_RADIUS_TOKENS,
        DEFAULT_TYPOGRAPHY_TOKENS,
        DEFAULT_MOTION_TOKENS,
        DEFAULT_STATE_TOKENS,
    ):
        for key in defaults:
            assert key in merged

    # Required colour tokens pass through via the palette itself.
    for name in REQUIRED_COLOUR_TOKEN_NAMES:
        assert name in merged


def test_with_token_defaults_lets_app_values_win_across_every_category():
    palette = {
        **_COMPLETE_PALETTE,
        "spaceMd": 99,
        "radiusMd": 1,
        "fontSizeMd": 2,
        "motionFast": 3,
        "stateIdleBg": "#custom",
    }

    merged = with_token_defaults(palette)

    assert merged["spaceMd"] == 99
    assert merged["radiusMd"] == 1
    assert merged["fontSizeMd"] == 2
    assert merged["motionFast"] == 3
    assert merged["stateIdleBg"] == "#custom"


def test_with_token_defaults_falls_back_to_engine_defaults_when_app_omits_a_category():
    """The transitional path: an app that hasn't adopted spacing/radius/
    typography/motion tokens yet still gets a coherent value, not a
    missing key — distinct from the required colour category, which
    hard-fails instead (see test_configure_app_qml_raises_on_incomplete_palette)."""
    merged = with_token_defaults(_COMPLETE_PALETTE)

    assert merged["spaceMd"] == DEFAULT_SPACING_TOKENS["spaceMd"]
    assert merged["radiusMd"] == DEFAULT_RADIUS_TOKENS["radiusMd"]
    assert merged["fontSizeMd"] == DEFAULT_TYPOGRAPHY_TOKENS["fontSizeMd"]
    assert merged["motionFast"] == DEFAULT_MOTION_TOKENS["motionFast"]
