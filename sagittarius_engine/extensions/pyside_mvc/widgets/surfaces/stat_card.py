"""
@brief `StatCard` — a `Card` showing one headline figure.
"""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..style import StyleRole, apply_role, semantic_colour
from ..surface import Card


class Tone(Enum):
    """
    @brief Whether a figure reads as good, bad, or merely a number.

    @details A semantic name, not a colour. The reference consumer computes
    `BULL_COLOR if net_profit >= 0 else BEAR_COLOR` upstream and hands the
    widget a raw hex string — which is exactly the "a literal with extra
    steps" pattern the token vocabulary exists to end. The comparison stays
    upstream, where the domain knowledge is; only its *answer* crosses into
    the widget, and this package decides what green means.
    """

    NEUTRAL = auto()
    POSITIVE = auto()
    NEGATIVE = auto()


_TONE_TOKENS: dict[Tone, str] = {
    Tone.NEUTRAL: "textPrimary",
    Tone.POSITIVE: "success",
    Tone.NEGATIVE: "danger",
}


class StatCard(Card):
    """
    @brief A `Card` with a headline value, an optional unit suffix, an
    optional badge, and an optional caption line beneath.

    @details
    Covers both shapes the reference consumer hand-rolls: its metric cards
    (title + value + suffix + coloured badge, ×2 call sites) and its stat
    tiles (label + value + a small caption line, ×2 call sites). Neither
    needs the other's extras, so all three are optional and hidden when
    empty rather than split into two classes over what is one card with
    slots.

    Two behaviours of the metric card are **not** reproduced, both because
    they have one call site rather than two: its always-drawn, unconfigurable
    `info` icon (no tooltip, no click — decorative), and its value font
    shrinking 18px→16px past ten characters. The second is a real usability
    fix and is recorded in `EPIC-007B` as a candidate; it needs a font-size
    token before it can be expressed here without a literal.
    """

    def __init__(
        self,
        title: str,
        *,
        value: str = "",
        suffix: str = "",
        caption: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)

        value_row = QHBoxLayout()
        self._value_label = QLabel(value)
        value_row.addWidget(self._value_label)

        self._suffix_label = QLabel(suffix)
        apply_role(self._suffix_label, StyleRole.SECTION_LABEL)
        self._suffix_label.setVisible(bool(suffix))
        value_row.addWidget(self._suffix_label)

        self._badge_label = QLabel()
        apply_role(self._badge_label, StyleRole.BADGE)
        self._badge_label.setVisible(False)
        value_row.addWidget(self._badge_label)

        value_row.addStretch(1)
        self.body_layout.addLayout(value_row)

        self._caption_label = QLabel(caption)
        apply_role(self._caption_label, StyleRole.SECTION_LABEL)
        self._caption_label.setVisible(bool(caption))
        self.body_layout.addWidget(self._caption_label)

        self.set_value(value)

    @property
    def value(self) -> str:
        return self._value_label.text()

    @property
    def caption(self) -> str:
        return self._caption_label.text()

    @property
    def badge_text(self) -> str:
        return self._badge_label.text()

    def set_value(self, value: str, *, tone: Tone = Tone.NEUTRAL) -> None:
        """@brief Sets the headline figure and how it should read."""
        self._value_label.setText(value)
        self._value_label.setStyleSheet(
            f"color: {semantic_colour(_TONE_TOKENS[tone])};"
        )

    def set_suffix(self, suffix: str) -> None:
        self._suffix_label.setText(suffix)
        self._suffix_label.setVisible(bool(suffix))

    def set_caption(self, caption: str) -> None:
        self._caption_label.setText(caption)
        self._caption_label.setVisible(bool(caption))

    def set_badge(self, text: str, *, tone: Tone = Tone.NEUTRAL) -> None:
        """@brief Sets the small pill beside the value, hiding it when
        `text` is empty — the same "empty means absent" contract the
        consumer's metric card already uses for its badge and suffix."""
        self._badge_label.setText(text)
        self._badge_label.setVisible(bool(text))
        if not text:
            return
        apply_role(self._badge_label, StyleRole.BADGE)
        # Appended, not rebuilt: `BADGE` renders a flat property list with no
        # selector, so a later `color:` overrides the role's own by ordinary
        # CSS last-declaration-wins. This would silently stop working if
        # `BADGE` ever grew a `QLabel { ... }` selector — a test pins the
        # tone actually reaching the rendered QSS.
        self._badge_label.setStyleSheet(
            f"{self._badge_label.styleSheet()}color: "
            f"{semantic_colour(_TONE_TOKENS[tone])};"
        )
