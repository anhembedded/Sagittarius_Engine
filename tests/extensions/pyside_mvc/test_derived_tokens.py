"""Tests for `tokens.derived.derive_shade_tokens` — `EPIC-008A`.

Pure Python, no Qt import in the module under test, so these run without
`QT_QPA_PLATFORM=offscreen` or a `QApplication`.
"""

from sagittarius_engine.extensions.pyside_mvc.tokens.derived import (
    derive_shade_tokens,
    derive_structural_tokens,
)

_BASE = {
    "accent": "#5980a6",
    "success": "#3ecf8e",
    "warning": "#e0a23c",
    "danger": "#a2402f",
    # Not one of the four ramped names — must never produce a ramp.
    "bg": "#f2f2f3",
}


def test_produces_all_nine_ramp_steps_for_each_ramped_colour():
    derived = derive_shade_tokens(_BASE)

    for name in ("accent", "success", "warning", "danger"):
        for step in (100, 200, 300, 400, 500, 600, 700, 800, 900):
            assert f"{name}{step}" in derived


def test_step_500_is_the_base_colour_unchanged():
    derived = derive_shade_tokens(_BASE)

    assert derived["danger500"] == "#a2402f"
    assert derived["accent500"] == "#5980a6"


def test_ramp_lightens_below_500_and_darkens_above_500():
    derived = derive_shade_tokens(_BASE)

    def luminance(hex_value: str) -> float:
        value = hex_value.lstrip("#")
        r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

    steps = [100, 200, 300, 400, 500, 600, 700, 800, 900]
    lums = [luminance(derived[f"danger{step}"]) for step in steps]

    # Strictly decreasing luminance as the ramp climbs from 100 (near-white
    # tint) to 900 (near-black shade) — the whole point of a ramp.
    assert lums == sorted(lums, reverse=True)
    assert lums[0] > lums[4] > lums[-1]


def test_does_not_produce_a_ramp_for_a_non_ramped_token_name():
    derived = derive_shade_tokens(_BASE)

    assert "bg100" not in derived
    assert "bgFill" not in derived


def test_skips_a_ramped_name_absent_from_the_base_palette():
    partial = {"accent": "#5980a6"}

    derived = derive_shade_tokens(partial)

    assert "accent500" in derived
    assert "danger500" not in derived
    assert "dangerFill" not in derived


def test_fill_equals_the_base_colour():
    derived = derive_shade_tokens(_BASE)

    assert derived["dangerFill"] == "#a2402f"
    assert derived["accentFill"] == "#5980a6"


def test_on_fill_picks_white_text_for_a_dark_fill():
    # #a2402f is a dark, saturated red — white text reads better on it.
    derived = derive_shade_tokens({"danger": "#a2402f"})

    assert derived["onDanger"] == "#ffffff"


def test_on_fill_picks_black_text_for_a_light_fill():
    # A pale, light-theme-style warning tone — black text reads better.
    derived = derive_shade_tokens({"warning": "#f5d38a"})

    assert derived["onWarning"] == "#000000"


def test_text_variant_darkens_a_light_theme_style_base_colour():
    """Verified against `reference/handoff.md` §10's own light-theme
    `fault`/`fault-text` pair: `#a2402f` (danger here) -> a *darker*
    `dangerText`, because prose must read against a pale tint of it."""
    derived = derive_shade_tokens({"danger": "#a2402f"})

    def luminance(hex_value: str) -> float:
        value = hex_value.lstrip("#")
        r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

    assert luminance(derived["dangerText"]) < luminance("#a2402f")


def test_text_variant_lightens_a_dark_theme_style_base_colour():
    """Verified against `reference/handoff.md` §10's own dark-theme
    `fault`/`fault-text` pair: `#e08a76` -> a *lighter* `dangerText`,
    because prose must read against a dark tint of it in dark mode."""
    derived = derive_shade_tokens({"danger": "#e08a76"})

    def luminance(hex_value: str) -> float:
        value = hex_value.lstrip("#")
        r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

    assert luminance(derived["dangerText"]) > luminance("#e08a76")


def test_accepts_three_digit_hex():
    derived = derive_shade_tokens({"danger": "#f00"})

    assert derived["danger500"] == "#ff0000"


def test_does_not_mutate_its_input():
    original = dict(_BASE)

    derive_shade_tokens(_BASE)

    assert _BASE == original


_STRUCTURAL_BASE = {
    "bg": "#f2f2f3",
    "textPrimary": "#1d1f20",
    "danger": "#a2402f",
    "accent": "#5980a6",
}


def test_structural_tokens_computes_ink_triplet_from_text_primary():
    derived = derive_structural_tokens(_STRUCTURAL_BASE)

    assert (derived["inkR"], derived["inkG"], derived["inkB"]) == (29.0, 31.0, 32.0)


def test_structural_tokens_surface_and_chrome_sit_between_bg_and_ink():
    derived = derive_structural_tokens(_STRUCTURAL_BASE)

    def luminance(hex_value: str) -> float:
        value = hex_value.lstrip("#")
        r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

    bg_lum = luminance(_STRUCTURAL_BASE["bg"])
    ink_lum = luminance(_STRUCTURAL_BASE["textPrimary"])
    surface_lum = luminance(derived["surface"])
    chrome_lum = luminance(derived["chrome"])

    # A light bg over a dark ink: surface and chrome step down toward ink,
    # chrome further than surface (matches the reference's bg > surface >
    # chrome luminance ordering in both themes).
    assert bg_lum > surface_lum > chrome_lum > ink_lum


def test_structural_tokens_divider_is_ink_at_a_fixed_alpha():
    derived = derive_structural_tokens(_STRUCTURAL_BASE)

    assert derived["divider"].startswith("#1d1f20")
    assert len(derived["divider"]) == len("#1d1f20") + 2  # + 1-byte alpha


def test_structural_tokens_hatch_is_danger_at_a_fixed_alpha():
    derived = derive_structural_tokens(_STRUCTURAL_BASE)

    assert derived["hatch"].startswith("#a2402f")


def test_structural_tokens_grid_line_is_accent_at_a_fixed_alpha():
    derived = derive_structural_tokens(_STRUCTURAL_BASE)

    assert derived["gridLine"].startswith("#5980a6")


def test_structural_tokens_omits_surface_and_chrome_without_bg():
    derived = derive_structural_tokens({"textPrimary": "#1d1f20"})

    assert "surface" not in derived
    assert "chrome" not in derived
    # divider only needs textPrimary, so it's still produced.
    assert "divider" in derived


def test_structural_tokens_omits_everything_without_text_primary():
    derived = derive_structural_tokens({"bg": "#f2f2f3", "danger": "#a2402f"})

    assert "surface" not in derived
    assert "chrome" not in derived
    assert "divider" not in derived
    assert "inkR" not in derived
    # hatch only needs danger, independent of textPrimary.
    assert "hatch" in derived


def test_structural_tokens_omits_hatch_and_grid_line_when_absent():
    derived = derive_structural_tokens({"bg": "#f2f2f3", "textPrimary": "#1d1f20"})

    assert "hatch" not in derived
    assert "gridLine" not in derived


def test_structural_tokens_does_not_mutate_its_input():
    original = dict(_STRUCTURAL_BASE)

    derive_structural_tokens(_STRUCTURAL_BASE)

    assert _STRUCTURAL_BASE == original
