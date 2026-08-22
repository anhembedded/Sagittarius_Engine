"""
@brief The UI Engine's Widget Kit layer — QML components (`QmlShared/`) and
the guard that keeps a consuming app off raw Qt Quick Controls primitives.
See `ui-architecture.md` §1/§3 and `Tasks/epics/EPIC-001_ui_engine_foundation/`.

@details
The QML components themselves still live in `QmlShared/` (the existing,
working location — see `EPIC-001A`'s "grow in place, no flag-day change"
decision). This package holds the kit's *Python*-side tooling only, the
same split `tokens/` already established between vocabulary/enforcement
code and the QML that consumes it.
"""

#: Imported for its `@QmlElement` side effect as much as for the symbol —
#: registering `CardModel` into the `Sagittarius.UI` QML URI happens at
#: module import time, and `pyside_mvc/__init__.py` imports this package,
#: so the type is always registered before any QML can load.
from .card_model import FALLBACK_BADGE_TEXT, CardModel
from .raw_primitive_guard import (
    RawPrimitiveFinding,
    find_raw_primitives,
    format_findings,
)
from .rectangle_card_guard import RectangleCardFinding, find_rectangle_as_styled_cards

__all__ = [
    "FALLBACK_BADGE_TEXT",
    "CardModel",
    "RawPrimitiveFinding",
    "RectangleCardFinding",
    "find_raw_primitives",
    "find_rectangle_as_styled_cards",
    "format_findings",
]
