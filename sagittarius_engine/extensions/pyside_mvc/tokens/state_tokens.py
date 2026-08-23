"""
@brief Default values for the "UI state" token vocabulary (enabled/disabled,
hover, active) shared QML components in this package bind against.

@details
Mirrors ThemeBridge's own contract: the engine has no opinion on an app's
actual color vocabulary (see theme_bridge.py's docstring), but a QML file
living in `sagittarius_engine` still needs *something* to bind to before any
app has configured its own palette — these are that fallback, deliberately
generic rather than styled after any one consuming app. A real app overrides
any subset of these keys via the same `ui_palette` dict it already passes to
`configure_app_qml()` (e.g. `Palette.as_ui_dict()`).
"""

#: QML property name -> default value. Consuming apps override any subset of
#: these through their own `as_ui_dict()`-style palette dict.
DEFAULT_STATE_TOKENS: dict[str, str | float] = {
    #: Opacity applied to a disabled control (background AND its icon/text
    #: alike — one token feeds both, so a disabled look can't drift into an
    #: unintended compounded opacity the way per-widget hand-rolled values
    #: have in the past).
    "stateDisabledOpacity": 0.45,
    #: Background color while hovered (and otherwise enabled/interactive).
    "stateHoverBg": "#2a2a2a",
    #: Background color at rest (enabled, not hovered).
    "stateIdleBg": "#202020",
    #: Background tint for an "active"/"selected" control (e.g. the current
    #: nav route) — expected to be a translucent color so it reads as a tint
    #: over `stateIdleBg`, not a solid fill.
    "stateActiveTint": "#331e90ff",
    #: Border color for an active/selected nav-style item that isn't using
    #: the app's semantic `accent` token for its border.
    "stateNavBorder": "#2a2a2a",
}


def with_state_token_defaults(
    palette: dict[str, str] | None,
) -> dict[str, str | float]:
    """
    @brief Merges an app-supplied palette dict with the engine's state-token
    defaults, app values winning on any key collision.
    @details A pure function (no singleton involved) so it's testable in
    isolation from `get_theme_bridge()`'s session-scoped, first-call-wins
    contract — see that function's own docstring for why callers after the
    first are otherwise silently ignored.

    Return type is `str | float`, not `str`: `DEFAULT_STATE_TOKENS` includes
    `stateDisabledOpacity` (a real `float`, bound to QML `opacity:` — see
    `StatefulButton.qml`), so a result typed all-`str` was never accurate.
    `palette` itself stays colour-only (`dict[str, str]`) — no consuming app
    is expected to override the opacity token; nothing here requires one to.
    """
    return {**DEFAULT_STATE_TOKENS, **(palette or {})}
