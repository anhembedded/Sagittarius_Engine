"""
@brief `CardModel` — the Python-side state and display logic behind every
`BaseCard`. QML declares values; this class derives everything computed
from them.

@details
Design decision (2026-08-23, user's call after weighing both options):
**QML is skin.** Any derivation — not just I/O or threading — belongs in
Python where it is debuggable with a real breakpoint, checkable by `mypy`,
and unit-testable without constructing a `QApplication` or rendering
anything. An earlier iteration computed the compact badge letter inline in
QML (`title.charAt(0).toUpperCase()`); small, but the wrong side of the
line, and the kind of thing that accumulates.

One shared model type for every card rather than one per card: `title`,
`icon` and `compact` mean the same thing on every `BaseCard` descendant, so
per-`ui-architecture.md` §1.2 they belong to one type used N times, not N
types. A per-card Python class would also fragment `compact` — an app-wide
toggle — into N independent copies that can silently disagree, the failure
mode `code-rule.md` §3 already names.

Registered as a QML-instantiable type (`@QmlElement`) into the same
`Sagittarius.UI` URI the file-based `qmldir` serves, so `BaseCard` can
declare its own instance inline and never has a null model to guard
against. Verified both resolution paths coexist under that one import.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal

#: Consumed by PySide6's `@QmlElement` — registers into the same URI the
#: file-based `Sagittarius/UI/qmldir` already serves, so a consumer needs
#: exactly one `import Sagittarius.UI 1.0` for both QML components and
#: Python-backed types.
QML_IMPORT_NAME = "Sagittarius.UI"
QML_IMPORT_MAJOR_VERSION = 1

#: Rendered in compact mode when a card supplies neither an icon nor a
#: title. A visible placeholder beats an empty badge: an empty square reads
#: as a rendering bug, "?" reads as missing metadata and prompts a fix.
FALLBACK_BADGE_TEXT = "?"

try:
    from PySide6.QtQml import QmlElement
except ImportError:  # pragma: no cover - PySide6 always ships QtQml in practice

    def QmlElement(cls):  # type: ignore[misc]
        return cls


@QmlElement
class CardModel(QObject):
    """
    @brief Display state for one card: its identity (`title`, `icon`), the
    app-wide `compact` toggle, and every value derived from those.

    @details
    Deliberately holds no reference to the consuming application, its
    engine, or any domain service (`ui-architecture.md` §1.2 tier 3) — it is
    constructible standalone in a test, a preview, or the gallery with no
    setup at all.
    """

    titleChanged = Signal()
    iconChanged = Signal()
    compactChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._title = ""
        self._icon = ""
        self._compact = False

    # ---- Inputs: declared per card ------------------------------------

    def _get_title(self) -> str:
        return self._title

    def _set_title(self, value: str) -> None:
        if value == self._title:
            return
        self._title = value
        self.titleChanged.emit()

    #: The card's display name. Also the compact-badge fallback source when
    #: no icon is set. Empty is valid, not an error — see FALLBACK_BADGE_TEXT.
    title = Property(str, _get_title, _set_title, notify=titleChanged)

    def _get_icon(self) -> str:
        return self._icon

    def _set_icon(self, value: str) -> None:
        if value == self._icon:
            return
        self._icon = value
        self.iconChanged.emit()

    #: Icon name resolved as `image://icons/<icon>/<tint>`, the same scheme
    #: `StatefulButton` uses. Empty means "none supplied".
    icon = Property(str, _get_icon, _set_icon, notify=iconChanged)

    def _get_compact(self) -> bool:
        return self._compact

    def _set_compact(self, value: bool) -> None:
        if value == self._compact:
            return
        self._compact = value
        self.compactChanged.emit()

    #: App-wide compact/full toggle. This type holds the value but has no
    #: opinion on *when* it flips — the consuming app owns that decision and
    #: binds one shared source into every card, exactly as `controlsEnabled`
    #: already works for screen controls.
    compact = Property(bool, _get_compact, _set_compact, notify=compactChanged)

    # ---- Derived: computed here, never in QML -------------------------

    def _get_show_icon(self) -> bool:
        return self._icon != ""

    #: Whether compact mode should render the icon rather than the letter
    #: badge. QML binds `visible:` to this instead of re-deriving
    #: `icon !== ""` at each of the two call sites.
    showIcon = Property(bool, _get_show_icon, notify=iconChanged)

    def _get_badge_text(self) -> str:
        if not self._title:
            return FALLBACK_BADGE_TEXT
        return self._title[0].upper()

    #: The letter shown in compact mode when no icon is set. Python rather
    #: than a QML `charAt(0).toUpperCase()` expression: unit-testable
    #: without Qt, and the single place to change if the rule ever grows
    #: (initials from two words, locale-aware casing, etc.).
    badgeText = Property(str, _get_badge_text, notify=titleChanged)
