"""
@brief The engine's fixed semantic design-token vocabulary — names the
engine owns, values a consuming app supplies.

@details
Reverses the previous model (`get_theme_bridge()` accepting an arbitrary
palette dict with no engine-side opinion on keys): the engine now defines
*which* semantic tokens exist, and validates that a consuming app filled the
required ones, rather than silently exposing whatever partial dict it was
given. See `ui-architecture.md` §2.1 and `EPIC-001A`/`EPIC-001B`.

Only the **colour** category is required at bootstrap. It is the one
category every real consumer of this engine already fully supplies today
(`Palette.as_ui_dict()` in the reference consumer already provides exactly
these ten keys) and the one category where drift was actually measured —
hundreds of hardcoded colour literals against a handful of official tokens,
including a near-duplicate accent colour nobody intended to create. Making
colour required, and only colour, fixes the measured problem without
breaking a consumer that has not yet adopted spacing/radius/typography/
motion tokens — see `defaults.py` for how those categories degrade to
engine-supplied defaults instead of hard-failing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenSpec:
    """One entry in the engine's semantic token vocabulary."""

    name: str
    category: str
    description: str


#: A consuming app's `ui_palette` (the dict passed to `configure_app_qml()`)
#: MUST supply every one of these. No engine-side default exists for them —
#: a literal default accent colour would just be a hidden literal with extra
#: steps, and colour is specifically the app's own visual identity.
REQUIRED_COLOUR_TOKENS: tuple[TokenSpec, ...] = (
    TokenSpec("bg", "colour", "Application background"),
    TokenSpec("bgSidebar", "colour", "Sidebar / navigation background"),
    TokenSpec("bgCard", "colour", "Card / panel background"),
    TokenSpec("bgCardHeader", "colour", "Card header background"),
    TokenSpec("border", "colour", "Default border colour"),
    TokenSpec("textPrimary", "colour", "Primary text colour"),
    TokenSpec("accent", "colour", "Accent / brand colour"),
    TokenSpec("success", "colour", "Success / positive semantic colour"),
    TokenSpec("warning", "colour", "Warning / caution semantic colour"),
    TokenSpec("danger", "colour", "Danger / negative semantic colour"),
    TokenSpec("muted", "colour", "Muted / secondary text or icon colour"),
)

#: `warning` joined the required set in EPIC-007B, and it is the one entry
#: added after a consumer already shipped — so it is worth saying why it is
#: required rather than optional, given that adding it breaks every app that
#: does not supply it.
#:
#: The reference consumer had two banners ("stale results", "coverage gap")
#: rendering `#2a1c07` / `#d97706` / `#fbbf24` as inline literals, in a
#: codebase whose whole token effort exists to remove inline literals. That
#: amber is neither `accent` (its brand yellow) nor `danger` (its red): a
#: warning banner sitting next to an accent-coloured info banner has to read
#: as a different thing, so folding the two together would have destroyed a
#: distinction the UI actually makes, not merely shifted a pixel value.
#:
#: Optional-with-a-default was the obvious cheaper route and was rejected on
#: this module's own stated grounds — an engine-supplied default colour "would
#: just be a hidden literal with extra steps". Three semantic states (success,
#: warning, danger) is also the smallest set that is not lopsided; shipping
#: two thirds of it was the actual anomaly.

REQUIRED_COLOUR_TOKEN_NAMES: frozenset[str] = frozenset(
    spec.name for spec in REQUIRED_COLOUR_TOKENS
)


class MissingRequiredTokensError(ValueError):
    """
    @brief Raised by `configure_app_qml()` when a consuming app's palette is
    missing one or more required tokens.
    @details A specific, named exception rather than a generic `ValueError`
    or `KeyError` so a caller (or a test asserting the failure mode) can
    catch exactly this condition. `missing` is exposed as a sorted tuple so
    the error message and any programmatic handling agree on ordering.
    """

    def __init__(self, missing: list[str]):
        self.missing = tuple(sorted(missing))
        joined = ", ".join(self.missing)
        super().__init__(
            "configure_app_qml() palette is missing required token(s): "
            f"{joined}. Every required colour token must be supplied — see "
            "tokens.vocabulary.REQUIRED_COLOUR_TOKENS."
        )


def missing_required_tokens(palette: Mapping[str, object]) -> list[str]:
    """
    @brief Returns the required token names absent from `palette`, sorted.
    @details A pure function, independent of any bootstrap side effect, so
    the completeness check is testable without constructing a QML engine.
    """
    return sorted(name for name in REQUIRED_COLOUR_TOKEN_NAMES if name not in palette)
