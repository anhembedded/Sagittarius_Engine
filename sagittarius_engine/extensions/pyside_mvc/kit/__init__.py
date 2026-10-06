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

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .gallery_coverage_guard import (
    DEFAULT_EXEMPT_TYPES,
    MissingFromGalleryFinding,
    find_types_missing_from_gallery,
    registered_types,
)
from .raw_primitive_guard import (
    RawPrimitiveFinding,
    find_raw_primitives,
    format_findings,
)
from .rectangle_card_guard import RectangleCardFinding, find_rectangle_as_styled_cards

if TYPE_CHECKING:
    from .card_model import FALLBACK_BADGE_TEXT, CardModel

#: `CardModel` defines `QtCore.Property`s, and PySide6 6.9-6.11 leaks one
#: uncollectable object per such class that is alive at interpreter exit
#: (BUG-023). So `card_model` loads only when one of these names is first
#: used, not when this package (or `pyside_mvc/__init__.py`) is imported.
#: Its `@QmlElement` registration into `Sagittarius.UI` happens at that
#: import, so `runtime/qml_host_view.py` -- the one place QML gets loaded --
#: imports `card_model` itself, before any QML can run.
_LAZY = {"CardModel": ".card_model", "FALLBACK_BADGE_TEXT": ".card_model"}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        value = getattr(import_module(_LAZY[name], __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_EXEMPT_TYPES",
    "FALLBACK_BADGE_TEXT",
    "CardModel",
    "MissingFromGalleryFinding",
    "RawPrimitiveFinding",
    "RectangleCardFinding",
    "find_raw_primitives",
    "find_rectangle_as_styled_cards",
    "find_types_missing_from_gallery",
    "format_findings",
    "registered_types",
]
