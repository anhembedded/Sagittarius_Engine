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
    #: A `Surface` that is also clickable and can be the user's current
    #: choice among siblings (`SelectableCard`) — e.g. one row of a picker
    #: list. Distinct from `SURFACE` because it needs a `WidgetState.SELECTED`
    #: rendering `SURFACE` has no reason to define.
    SELECTABLE_CARD = auto()
    PRIMARY_BUTTON = auto()
    SECONDARY_BUTTON = auto()
    DANGER_BUTTON = auto()
    CHECKBOX = auto()
    FIELD = auto()

    # --- EPIC-007B ----------------------------------------------------- #
    # Every one below needs its own `if` branch in `_build_qss()`. There is
    # no default: the function ends in a dict lookup over the three button
    # roles, so a role added here without a branch raises `KeyError` the
    # first time a widget is constructed, not when the enum is defined.
    # That fail-fast is `controls.py`'s deliberate choice, kept — but it
    # means "add the enum entry" is half the change, never all of it.

    #: A small pill carrying a count or a short status word, sitting beside
    #: a label (`LogPanel`'s "340 EVENTS", a `TabBar` tab's count). Reads
    #: `SELECTED` as its emphasised form.
    BADGE = auto()
    #: The three banner severities. Separate roles rather than one `BANNER`
    #: role plus a severity argument, because `apply_role()` takes a role and
    #: a `WidgetState`, and severity is not a state — a banner does not
    #: transition between info and danger the way a button transitions
    #: between normal and disabled.
    BANNER_INFO = auto()
    BANNER_WARN = auto()
    BANNER_DANGER = auto()
    #: A small muted all-caps heading over a group of content.
    SECTION_LABEL = auto()
    #: The column-header strip of a `TableCard`.
    TABLE_HEADER = auto()
    PROGRESS = auto()


class WidgetState(Enum):
    """Structural state `apply_role()` renders differently. Not every role
    uses every state — a `FIELD` has no hover-vs-idle distinction the way a
    `PRIMARY_BUTTON` does, `_build_qss()` simply ignores states a role's
    QSS block has no rule for."""

    NORMAL = auto()
    DISABLED = auto()
    #: Rendered only by `StyleRole.SELECTABLE_CARD` — "this is the user's
    #: current choice among its siblings," an accent border/background, not
    #: to be confused with keyboard/mouse `:hover` (Qt's own pseudo-state,
    #: still expressed via a `:hover` selector in that role's QSS block).
    SELECTED = auto()


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


def semantic_colour(name: str) -> str:
    """
    @brief Reads one semantic colour token by name.

    @details The escape hatch for the case `apply_role()` cannot express: a
    colour chosen per *instance* rather than per *role*. `StatCard`'s value
    is the motivating one — whether a figure reads positive or negative is
    decided per card at runtime, and encoding it as roles would mean a
    `POSITIVE_VALUE`/`NEGATIVE_VALUE`/`NEUTRAL_VALUE` triple for every place
    that ever needs a tone.

    Returns a token value, never a literal, so `guards.find_inline_stylesheets`
    stays satisfied and a palette change still reaches every caller. Prefer
    `apply_role()` wherever the colour is a property of what the widget *is*.

    @raise KeyError If no such token exists — same fail-fast as an unknown
    role, rather than rendering a widget with an empty colour.
    """
    return _token(name)


def _token(name: str) -> str:
    """Reads one token value from the shared theme bridge as a string —
    every token this module reads is either a colour (already `str`) or a
    spacing/radius pixel value (`float`, needs `px` appended for QSS)."""
    value = get_theme_bridge().value(name)
    return str(value)


def _px(name: str) -> str:
    return f"{_token(name)}px"


#: Which semantic colour token each banner severity reads. A mapping rather
#: than three near-identical `if` bodies — the three banners differ only in
#: this one token, and writing them out separately invites the drift where
#: one severity quietly grows a rule the other two lack.
_BANNER_ACCENTS: dict[StyleRole, str] = {
    StyleRole.BANNER_INFO: "accent",
    StyleRole.BANNER_WARN: "warning",
    StyleRole.BANNER_DANGER: "danger",
}


def _build_qss(role: StyleRole, state: WidgetState) -> str:
    disabled = state is WidgetState.DISABLED

    if role is StyleRole.SURFACE:
        return (
            f"background-color: {_token('bgCard')};"
            f"border: 1px solid {_token('border')};"
            f"border-radius: {_px('radiusMd')};"
            f"color: {_token('textPrimary')};"
        )

    if role is StyleRole.SELECTABLE_CARD:
        selected = state is WidgetState.SELECTED
        border_color = _token("accent") if selected else _token("border")
        background = _token("stateActiveTint") if selected else "transparent"
        return (
            f"QFrame {{"
            f"background-color: {background};"
            f"border: 1px solid {border_color};"
            f"border-radius: {_px('radiusMd')};"
            f"}}"
            f"QFrame:hover {{background-color: {_token('stateHoverBg')};}}"
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

    if role is StyleRole.BADGE:
        emphasised = state is WidgetState.SELECTED
        return (
            f"background-color: "
            f"{_token('stateActiveTint') if emphasised else _token('stateIdleBg')};"
            f"border: 1px solid "
            f"{_token('accent') if emphasised else _token('border')};"
            f"border-radius: {_px('radiusSm')};"
            f"color: {_token('accent') if emphasised else _token('muted')};"
            f"padding: 0 {_px('spaceXs')};"
        )

    if role in _BANNER_ACCENTS:
        banner_accent = _token(_BANNER_ACCENTS[role])
        return (
            f"background-color: {_token('bgCardHeader')};"
            f"border: 1px solid {banner_accent};"
            f"border-radius: {_px('radiusMd')};"
            f"color: {banner_accent};"
        )

    if role is StyleRole.SECTION_LABEL:
        return f"background-color: transparent;color: {_token('muted')};"

    if role is StyleRole.TABLE_HEADER:
        return (
            f"background-color: {_token('bgCardHeader')};"
            f"border-radius: {_px('radiusSm')};"
            f"color: {_token('muted')};"
        )

    if role is StyleRole.PROGRESS:
        return (
            f"QProgressBar {{"
            f"background-color: {_token('stateIdleBg')};"
            f"border: 1px solid {_token('border')};"
            f"border-radius: {_px('radiusSm')};"
            f"color: {_token('textPrimary')};"
            f"text-align: center;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"background-color: {_token('muted') if disabled else _token('accent')};"
            f"border-radius: {_px('radiusSm')};"
            f"}}"
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
