"""Tests for CardModel — the Python-side card display logic.

The point of moving this derivation out of QML: it is testable here with
no QApplication, no QQuickWidget, no rendering, no offscreen platform. If
these ever need Qt to run, the logic has leaked back into the view layer.
"""

from __future__ import annotations

import pytest

from sagittarius_engine.extensions.pyside_mvc.kit.card_model import (
    FALLBACK_BADGE_TEXT,
    CardModel,
)


def test_defaults_are_empty_and_full_size():
    model = CardModel()

    assert model.title == ""
    assert model.icon == ""
    assert model.compact is False


def test_badge_text_is_the_uppercased_first_letter_of_title():
    model = CardModel()
    model.title = "Positions"

    assert model.badgeText == "P"


def test_badge_text_uppercases_a_lowercase_title():
    model = CardModel()
    model.title = "positions"

    assert model.badgeText == "P"


def test_badge_text_falls_back_when_there_is_no_title():
    model = CardModel()

    assert model.badgeText == FALLBACK_BADGE_TEXT


def test_badge_text_handles_a_single_character_title():
    """Guards the off-by-one that a naive `title[0:1]`-style slice or an
    index-based implementation could get wrong on a 1-char string."""
    model = CardModel()
    model.title = "x"

    assert model.badgeText == "X"


def test_badge_text_uses_the_first_character_of_a_multi_word_title():
    """Today's rule is deliberately first-character, not initials — pinned
    so a future change to initials is a conscious decision that breaks this
    test, not a silent behaviour drift."""
    model = CardModel()
    model.title = "Time Range"

    assert model.badgeText == "T"


def test_show_icon_is_false_without_an_icon():
    model = CardModel()
    model.title = "Log"

    assert model.showIcon is False


def test_show_icon_is_true_once_an_icon_is_set():
    model = CardModel()
    model.icon = "scroll-text"

    assert model.showIcon is True


def test_an_icon_wins_over_the_title_letter():
    """Both set: showIcon decides, and badgeText stays available but unused
    by the view. Documents the precedence rather than leaving it implied."""
    model = CardModel()
    model.title = "Log"
    model.icon = "scroll-text"

    assert model.showIcon is True
    assert model.badgeText == "L"


@pytest.mark.parametrize(
    "attribute, signal_name, first, second",
    [
        ("title", "titleChanged", "Log", "Positions"),
        ("icon", "iconChanged", "scroll-text", "table"),
        ("compact", "compactChanged", True, False),
    ],
)
def test_setting_a_new_value_emits_its_change_signal(
    attribute, signal_name, first, second
):
    model = CardModel()
    emissions = []
    getattr(model, signal_name).connect(lambda: emissions.append(True))

    setattr(model, attribute, first)
    assert len(emissions) == 1

    setattr(model, attribute, second)
    assert len(emissions) == 2


@pytest.mark.parametrize(
    "attribute, signal_name, value",
    [
        ("title", "titleChanged", "Log"),
        ("icon", "iconChanged", "table"),
        ("compact", "compactChanged", True),
    ],
)
def test_setting_the_same_value_again_emits_nothing(attribute, signal_name, value):
    """Without this guard every re-assignment would re-notify, re-running
    every bound QML expression for no change — the kind of avoidable churn
    that only shows up as sluggishness under a live-updating screen."""
    model = CardModel()
    setattr(model, attribute, value)

    emissions = []
    getattr(model, signal_name).connect(lambda: emissions.append(True))
    setattr(model, attribute, value)

    assert emissions == []


def test_badge_text_updates_when_the_title_changes():
    model = CardModel()
    model.title = "Log"
    assert model.badgeText == "L"

    model.title = "Positions"
    assert model.badgeText == "P"


def test_model_needs_no_application_or_engine_reference():
    """ui-architecture.md §1.2 tier 3: constructible standalone. If this
    ever requires setup, the model has acquired a dependency it must not
    have."""
    assert CardModel().badgeText == FALLBACK_BADGE_TEXT
