"""
@brief Engine-supplied defaults for the token categories that are not yet
required (spacing, radius, typography, motion) — plus the merge that
combines them with the existing state-token defaults and an app's palette.

@details
Colour is the only required category (`vocabulary.py`) because it is the
only one every real consumer already fully supplies. These four categories
are new vocabulary this epic introduces: a consumer that has not adopted
them yet still boots correctly against these generic defaults (the same
"not migrated yet, not wrong" transitional path `state_tokens.py` already
established for hover/active/disabled tokens) — see `ui-architecture.md`
§2.1's note distinguishing the two.

An app overrides any subset of these keys through the same `ui_palette`
dict it already passes to `configure_app_qml()` — one dict, one bootstrap
call, no separate registration path per category.
"""

from __future__ import annotations

from .state_tokens import with_state_token_defaults

#: 4/8/12/16/24 scale — the smallest unit is named, the rest are named
#: multiples rather than a bare numeric progression, so QML reads intent
#: ("spaceMd") instead of a magic number that happens to be 12.
DEFAULT_SPACING_TOKENS: dict[str, float] = {
    "spaceXs": 4,
    "spaceSm": 8,
    "spaceMd": 12,
    "spaceLg": 16,
    "spaceXl": 24,
}

DEFAULT_RADIUS_TOKENS: dict[str, float] = {
    "radiusSm": 4,
    "radiusMd": 6,
    "radiusLg": 10,
}

DEFAULT_TYPOGRAPHY_TOKENS: dict[str, float] = {
    "fontSizeSm": 11,
    "fontSizeMd": 13,
    "fontSizeLg": 16,
    #: The display tier — a stat card's headline figure, the one number a
    #: screen exists to show. Added by `EPIC-007F`: `StatCard` shipped with
    #: *no* size on its value at all, so the figure it calls a headline
    #: rendered at the widget default (9pt), because the scale stopped at
    #: `fontSizeLg` and there was no tier to name.
    "fontSizeXl": 20,
}

#: Durations in milliseconds — matches the 150-250ms micro-animation range
#: already established as house style for hover/press/transition feedback.
DEFAULT_MOTION_TOKENS: dict[str, float] = {
    "motionFast": 150,
    "motionNormal": 220,
}


def with_token_defaults(palette: dict[str, str] | None) -> dict[str, str | float]:
    """
    @brief Merges an app-supplied palette with every default-backed token
    category (state, spacing, radius, typography, motion), app values
    winning on any key collision.

    @details
    Required colour tokens are deliberately NOT included here — they have no
    engine default by design (see `vocabulary.py`) and are validated, not
    defaulted, at `configure_app_qml()`. This function only fills the
    categories that are allowed to degrade to a generic default.
    """
    merged: dict[str, str | float] = {}
    merged.update(DEFAULT_SPACING_TOKENS)
    merged.update(DEFAULT_RADIUS_TOKENS)
    merged.update(DEFAULT_TYPOGRAPHY_TOKENS)
    merged.update(DEFAULT_MOTION_TOKENS)
    # with_state_token_defaults() already merges its own defaults with
    # `palette`, app winning — reused as-is rather than duplicating that
    # merge logic, then the earlier categories' defaults are overlaid
    # underneath its result so app values still win across every category.
    state_merged = with_state_token_defaults(palette)
    merged.update(state_merged)
    return merged
