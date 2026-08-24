"""
@brief Composition-based styling for `pyside_mvc.widgets` — the QtWidgets
replacement for the QML kit's `Sagittarius/UI/` (EPIC-006, see
`Sagittarius_Elite_Warrior/Tasks/epics/EPIC-006_drop_qml/
DECISION_2026-08-24_widget_architecture.md`).

@details
`Surface`/`Card`/`Overlay` and each `Styled*` control share no common base
beyond their own single Qt lineage (`QFrame`/`QDialog`/`QPushButton`/...) —
PySide6/Shiboken forbids a class inheriting two QObject-derived bases, which
rules out a shared styling mixin across those lineages. `apply_role()` is
the composition that replaces it: every widget in this package calls it
once, in its own `__init__`, instead of inheriting styling behaviour.

This module is the ONLY place in `pyside_mvc.widgets` permitted to build a
stylesheet string from token values — the guard counterpart to the QML
kit's `tokens.qml_literal_guard` (`widgets.guards.find_inline_stylesheets`)
enforces that no other file in this package (or a consuming app's own
widgets, once it starts using this base) calls `setStyleSheet()` with a
hex literal or token value baked in directly.
"""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtWidgets import QWidget

from sagittarius_engine.extensions.pyside_mvc.tokens.theme_bridge import (
    get_theme_bridge,
)


class StyleRole(Enum):
    """
    @brief What a widget IS, not how it looks — `apply_role()` resolves the
    actual QSS from the role + the app's own token values.

    @details One entry per genuinely distinct visual treatment this package
    ships, not one per concrete widget class — `Surface`/`Card`/`Panel`/
    `Overlay` all read as the same "raised, bordered surface on the app
    background" in this app's existing dark theme (confirmed against
    EPIC-005's own dialogs, which all used `Palette.BG_CARD` +
    `Palette.TEXT_PRIMARY` for exactly this), so they share `SURFACE`
    rather than each inventing its own near-identical role.
    """

    SURFACE = auto()
    PRIMARY_BUTTON = auto()
    SECONDARY_BUTTON = auto()
    DANGER_BUTTON = auto()
    CHECKBOX = auto()
    FIELD = auto()


class WidgetState(Enum):
    """Structural state `apply_role()` renders differently. Not every role
    uses every state — a `FIELD` has no hover-vs-idle distinction the way a
    `PRIMARY_BUTTON` does, `_build_qss()` simply ignores states a role's
    QSS block has no rule for."""

    NORMAL = auto()
    DISABLED = auto()


def apply_role(
    widget: QWidget, role: StyleRole, *, state: WidgetState = WidgetState.NORMAL
) -> None:
    """
    @brief Applies token-driven QSS for `role` to `widget`.

    @details The only call a widget in this package makes to get styled —
    no widget here inherits styling behaviour from a shared base. Reads
    from the same `get_theme_bridge()` singleton QML's `Theme.*` bindings
    already read from, so a QtWidgets screen and a QML screen in the same
    app process render from one source of truth, not two independently
    maintained copies.

    @param widget Any QWidget — this package's own base classes call it on
    themselves; a consuming app's derived widget may call it again after
    `super().__init__()` to apply a different role than its base class did
    (e.g. a `DangerCard(Card)` re-applying `DANGER_BUTTON`-flavoured chrome
    to an internal action button `Card` itself doesn't know about).
    @param role Which visual treatment to apply.
    @param state Structural state to render — `WidgetState.DISABLED` is a
    static style choice for widgets whose disabled look needs more than
    Qt's default `:disabled` pseudo-state selector can express; ordinary
    `setEnabled(False)` should still be used for interaction disabling,
    this parameter only controls which QSS block `apply_role()` builds.

    @raise ValueError If no palette has been supplied yet — the app must
    call `sagittarius_engine.extensions.pyside_mvc.tokens.get_theme_bridge()`
    with its palette once at bootstrap (today: a side effect of
    `configure_app_qml()` + constructing the first QML-hosted view; a
    QtWidgets-only app with no QML screens at all must call
    `get_theme_bridge(palette)` directly itself instead — see
    `Sagittarius_Elite_Warrior`'s `EPIC-006C` for that wiring once it
    exists) before constructing any widget from this package.
    """
    widget.setStyleSheet(_build_qss(role, state))


def _token(name: str) -> str:
    """Reads one token value from the shared theme bridge as a string —
    every token this module reads is either a colour (already `str`) or a
    spacing/radius pixel value (`float`, needs `px` appended for QSS)."""
    value = get_theme_bridge().value(name)
    return str(value)


def _px(name: str) -> str:
    return f"{_token(name)}px"


def _build_qss(role: StyleRole, state: WidgetState) -> str:
    disabled = state is WidgetState.DISABLED

    if role is StyleRole.SURFACE:
        return (
            f"background-color: {_token('bgCard')};"
            f"border: 1px solid {_token('border')};"
            f"border-radius: {_px('radiusMd')};"
            f"color: {_token('textPrimary')};"
        )

    if role is StyleRole.CHECKBOX:
        return f"color: {_token('textPrimary')};"

    if role is StyleRole.FIELD:
        return (
            f"background-color: {_token('stateIdleBg')};"
            f"color: {_token('textPrimary')};"
            f"border: 1px solid {_token('border')};"
            f"border-radius: {_px('radiusSm')};"
            f"padding: 0 {_px('spaceSm')};"
        )

    accent = {
        StyleRole.PRIMARY_BUTTON: _token("accent"),
        StyleRole.SECONDARY_BUTTON: _token("border"),
        StyleRole.DANGER_BUTTON: _token("danger"),
    }[role]
    text_color = (
        _token("textPrimary") if role is StyleRole.SECONDARY_BUTTON else _token("bg")
    )
    background = _token("muted") if disabled else accent
    hover_background = (
        _token("stateHoverBg") if role is StyleRole.SECONDARY_BUTTON else background
    )
    return (
        f"QPushButton {{"
        f"background-color: {background};"
        f"color: {text_color};"
        f"border: 1px solid {accent};"
        f"border-radius: {_px('radiusSm')};"
        f"padding: {_px('spaceXs')} {_px('spaceMd')};"
        f"}}"
        f"QPushButton:hover {{background-color: {hover_background};}}"
    )
