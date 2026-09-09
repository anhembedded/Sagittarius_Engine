"""
@brief Tokens computed from the app's existing required colours, rather
than declared as additional literal tokens — `EPIC-008A`'s resolution of a
design handoff asking for `fault`/`fault-fill`/`on-fault`/`fault-text`,
`accent-100…900`/`neutral-100…900` ramps, and a handful of structural
colours (`surface`/`chrome`/`divider`/`hatch`/`gridLine`/`ink`) this engine
had no name for yet.

@details
`derive_shade_tokens()` handles the first half: `fault` reads, functionally,
as a shade/role variant of a colour the engine already names — `danger`
(`tokens/vocabulary.py`). Adding a parallel `fault` vocabulary would be two
names for one concept, and nine independent literal tokens per colour for
the ramps would be the token-count explosion `ui-architecture.md` §2.1
already warns about (that section's whole argument is "hundreds of colour
literals against a handful of official tokens" — replacing a handful of
tokens with ninety is the same failure shape, not a fix for it). A
consuming app therefore keeps supplying exactly its four semantic colours
(`accent`/`success`/`warning`/`danger`); every ramp step and role variant
is computed from those, once, at bootstrap.

`derive_structural_tokens()` handles the second half: `surface`/`chrome`
are genuinely new *names* (nothing today distinguishes "the background" from
"a slightly different background"), but their *values* are still computed
from `bg`/`textPrimary` rather than a colour a consuming app must separately
pick and keep in sync — and `divider`/`hatch`/`gridLine` turn out, on
inspection of the handoff's own token table, to be nothing more than an
existing colour (`textPrimary`/`danger`/`accent` respectively) composited
at one fixed alpha, so they need no independent value at all.

This module is pure Python — no Qt import — so the colour math is testable
without `QT_QPA_PLATFORM=offscreen` or a `QApplication`.
"""

from __future__ import annotations

from collections.abc import Mapping

#: The four required semantic colours a shade ramp is computed for. Not
#: `bg`/`border`/etc. — those are structural, not semantic-with-intensity,
#: and a "bg-100..900" ramp has no meaning the way "danger, but lighter" does.
_RAMPED_TOKEN_NAMES: tuple[str, ...] = ("accent", "success", "warning", "danger")

#: Ramp step -> how far to move from the base colour, and in which
#: direction. Negative = toward white (a tint, for light backgrounds/fills
#: behind text); positive = toward black (a shade, for text/borders that
#: must read against a light or neutral ground). 500 is the base colour
#: itself: the step a consumer reaches for when they mean "the colour",
#: with no direction to travel.
_RAMP_STEP_AMOUNTS: dict[int, float] = {
    100: -0.90,
    200: -0.75,
    300: -0.55,
    400: -0.30,
    500: 0.0,
    600: 0.18,
    700: 0.34,
    800: 0.48,
    900: 0.60,
}

#: `<name>Text` reaches further toward whichever extreme the base colour
#: already leans — it must stay readable as small prose on a *tinted*
#: banner (a light tint of the base over a light `bg`, or a dark tint over
#: a dark `bg`), which is a stronger and theme-direction-sensitive
#: requirement compared to a border or a tag background. See
#: `_text_shade_amount()`.
_TEXT_SHADE_MAGNITUDE = 0.40

#: Relative luminance (ITU-R BT.601 weights, adequate for a UI contrast
#: pick — this is not colour-managed output) at which a colour is "light
#: enough" that it reads as a dark-theme tone rather than a light-theme
#: one. Drives two decisions: whether black or white text sits better on a
#: fill of that colour, and which extreme `<name>Text` should lean further
#: toward (the same direction the base colour already leans).
_LIGHT_TONE_LUMINANCE_THRESHOLD = 0.6

_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _clamp_channel(value: float) -> int:
    return max(0, min(255, round(value)))


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{_clamp_channel(c):02x}" for c in rgb)


def _mix(
    rgb: tuple[int, int, int], target: tuple[int, int, int], amount: float
) -> tuple[float, float, float]:
    """@brief Moves `rgb` toward `target` by `amount` (0 = unchanged, 1 = `target`)."""
    r, g, b = rgb
    tr, tg, tb = target
    return (r + (tr - r) * amount, g + (tg - g) * amount, b + (tb - b) * amount)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _shade_step(rgb: tuple[int, int, int], amount: float) -> tuple[float, float, float]:
    """@brief `amount` < 0 tints toward white, > 0 shades toward black,
    0 leaves `rgb` unchanged (the ramp's own 500 step)."""
    if amount < 0:
        return _mix(rgb, _WHITE, -amount)
    if amount > 0:
        return _mix(rgb, _BLACK, amount)
    return rgb


def _text_shade_amount(rgb: tuple[int, int, int]) -> float:
    """@brief Direction and magnitude for `<name>Text`: push further
    toward whichever extreme `rgb` already leans, rather than always
    toward black.

    @details A light-theme semantic colour (mid/low luminance, meant to
    read against a light `bg`) needs prose *darker* than itself to stay
    legible on its own pale tinted banner; a dark-theme one (already light,
    meant to read against a dark `bg`) needs prose *lighter* than itself
    for the same reason on a dark tinted banner. Verified against both
    concrete values in `reference/handoff.md` §10: light `fault` `#a2402f`
    (luminance ≈0.36) darkens to `fault-text` `#7d3123`; dark `fault`
    `#e08a76` (luminance ≈0.63) lightens to `fault-text` `#f2b8a8`.
    """
    if _relative_luminance(rgb) >= _LIGHT_TONE_LUMINANCE_THRESHOLD:
        return -_TEXT_SHADE_MAGNITUDE
    return _TEXT_SHADE_MAGNITUDE


def derive_shade_tokens(base: Mapping[str, str]) -> dict[str, str]:
    """
    @brief For every semantic colour in `base` that has a ramp
    (`accent`/`success`/`warning`/`danger`), computes a 100-900 tint/shade
    ramp plus `<name>Fill`/`on<Name>`/`<name>Text` role variants.

    @details Silently skips any of the four names absent from `base` —
    callers in this codebase always supply all four (they are required
    colour tokens, `tokens/vocabulary.py`), but this function itself makes
    no such assumption, so it stays usable against a partial palette in a
    test or a future default-backed caller.

    @param base Semantic colour name -> hex string (`"#rrggbb"` or `"#rgb"`).
    @return New token names only — ramp steps (`danger100`..`danger900`) and
    role variants (`dangerFill`, `onDanger`, `dangerText`), never `base`'s
    own keys.
    """
    derived: dict[str, str] = {}
    for name in _RAMPED_TOKEN_NAMES:
        hex_value = base.get(name)
        if hex_value is None:
            continue
        rgb = _hex_to_rgb(hex_value)

        for step, amount in _RAMP_STEP_AMOUNTS.items():
            derived[f"{name}{step}"] = _rgb_to_hex(_shade_step(rgb, amount))

        fill_rgb = rgb
        on_fill_rgb = (
            _BLACK
            if _relative_luminance(fill_rgb) >= _LIGHT_TONE_LUMINANCE_THRESHOLD
            else _WHITE
        )
        capitalized = name[0].upper() + name[1:]
        derived[f"{name}Fill"] = _rgb_to_hex(fill_rgb)
        derived[f"on{capitalized}"] = _rgb_to_hex(on_fill_rgb)
        derived[f"{name}Text"] = _rgb_to_hex(_shade_step(rgb, _text_shade_amount(rgb)))

    return derived


#: How far `surface`/`chrome` move from `bg` toward `textPrimary` ("ink").
#: Deliberately tiny — the reference design's own `bg`/`surface`/`chrome`
#: triples differ by only a few hex digits in both themes (light:
#: `#f2f2f3`/`#e9e9ea`/`#e7e7ea`; dark: `#151d25`/`#1c262f`/`#232e38`), not a
#: full ramp step. Moving toward `ink` rather than a fixed white/black means
#: this self-adjusts for either theme: `ink` is dark-on-light in a light
#: palette and light-on-dark in a dark one, same as the two references.
_SURFACE_AMOUNT = 0.05
_CHROME_AMOUNT = 0.09

#: Fixed alpha for tokens that are, functionally, one existing colour
#: composited at a single constant opacity rather than an independent hue —
#: `reference/handoff.md` §10 names each of these as exactly that (`divider`
#: is "ink @ 16%", `hatch` is "fault @ 7-10%", `grid-line` is an accent tint).
_DIVIDER_INK_ALPHA = 0.18
_HATCH_DANGER_ALPHA = 0.08
_GRID_LINE_ACCENT_ALPHA = 0.12


def _hex_with_alpha(rgb: tuple[int, int, int], alpha: float) -> str:
    """@brief `"#rrggbbaa"` — Qt/QML's `color` type accepts an 8-digit hex
    string directly, so no `Qt.rgba()` composition is needed in QML for a
    token that only ever needs one fixed alpha."""
    alpha_byte = _clamp_channel(alpha * 255)
    r, g, b = rgb
    return _rgb_to_hex((float(r), float(g), float(b))) + f"{alpha_byte:02x}"


def derive_structural_tokens(base: Mapping[str, str]) -> dict[str, str | float]:
    """
    @brief Computes `surface`, `chrome`, `divider`, `hatch`, `gridLine`, and
    an `ink` RGB triplet (`inkR`/`inkG`/`inkB`, 0-255) from the app's
    existing `bg`/`textPrimary`/`danger`/`accent` — new token *names* for
    concepts genuinely absent from today's vocabulary (`ui-architecture.md`
    §2.1's other case: not everything is a duplicate to collapse, some of
    this really is new), but still zero new colours a consuming app must
    separately choose and keep in sync.

    @details `ink` is exposed as three separate numeric channels rather
    than one packed value: QML composites it at many different alphas
    (`reference/handoff.md` §10 lists a dozen), which needs `Qt.rgba(r, g,
    b, alpha)` — a single pre-baked hex string cannot serve that. `divider`/
    `hatch`/`gridLine` each need exactly one fixed alpha everywhere they're
    used, so those bake to an `"#rrggbbaa"` string instead, needing no QML
    composition at every call site the way an arbitrarily-alpha'd token
    would.

    @return Only the keys this function computes. Silently omits `surface`/
    `chrome`/`ink*` when `bg`/`textPrimary` are absent from `base`, and
    `hatch`/`gridLine` when `danger`/`accent` are absent — the same
    graceful-partial-input contract as `derive_shade_tokens`. `divider`
    needs `textPrimary` only (it is `ink` at a fixed alpha).
    """
    derived: dict[str, str | float] = {}

    ink_hex = base.get("textPrimary")
    if ink_hex is not None:
        ink_rgb = _hex_to_rgb(ink_hex)
        derived["inkR"], derived["inkG"], derived["inkB"] = (float(c) for c in ink_rgb)
        derived["divider"] = _hex_with_alpha(ink_rgb, _DIVIDER_INK_ALPHA)

        bg_hex = base.get("bg")
        if bg_hex is not None:
            bg_rgb = _hex_to_rgb(bg_hex)
            derived["surface"] = _rgb_to_hex(_mix(bg_rgb, ink_rgb, _SURFACE_AMOUNT))
            derived["chrome"] = _rgb_to_hex(_mix(bg_rgb, ink_rgb, _CHROME_AMOUNT))

    danger_hex = base.get("danger")
    if danger_hex is not None:
        derived["hatch"] = _hex_with_alpha(_hex_to_rgb(danger_hex), _HATCH_DANGER_ALPHA)

    accent_hex = base.get("accent")
    if accent_hex is not None:
        derived["gridLine"] = _hex_with_alpha(
            _hex_to_rgb(accent_hex), _GRID_LINE_ACCENT_ALPHA
        )

    return derived
