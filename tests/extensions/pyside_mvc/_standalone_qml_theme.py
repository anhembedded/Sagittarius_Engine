"""Shared helper for kit-component tests that need to tell theme colours
APART (`EPIC-008A`) — a standalone `QQmlEngine` with its own directly-
injected `Theme`, independent of the shared `get_theme_bridge()` singleton.

That singleton is first-call-wins for the whole pytest process, and every
fixture in `test_widget_kit_gallery.py` locks it to an all-`#000000`
placeholder palette — fine for "does this render", useless for "does state
X map to colour Y", since every candidate colour would be identical black.
Not a fixture (module-scoped or otherwise): each test that needs one
constructs its own via `standalone_theme_engine()`, since the objects it
returns must outlive everything created against `engine` for exactly as
long as that test needs them, which a shared fixture teardown ordering
cannot guarantee test-by-test.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlPropertyMap

from sagittarius_engine.extensions.pyside_mvc.tokens import with_token_defaults

PYSIDE_MVC_DIR = (
    Path(__file__).resolve().parents[3]
    / "sagittarius_engine"
    / "extensions"
    / "pyside_mvc"
)

#: Four genuinely distinguishable required colours -- the point is telling
#: `accent`/`accent700`/`danger`/`muted` (and their derived ramps/roles)
#: apart in a test assertion, which an all-black placeholder palette cannot
#: do.
DISTINCT_PALETTE = {
    "bg": "#111111",
    "bgSidebar": "#111111",
    "bgCard": "#111111",
    "bgCardHeader": "#111111",
    "border": "#222222",
    "textPrimary": "#eeeeee",
    "accent": "#3366ff",
    "success": "#22cc88",
    "warning": "#ffaa22",
    "danger": "#ff3355",
    "muted": "#888888",
}


def standalone_theme_engine(palette: dict[str, str] | None = None):
    """@brief A fresh `QQmlEngine` with `Theme` populated from `palette`
    (default `DISTINCT_PALETTE`) via the real `with_token_defaults()` (so
    derived tokens like `accent700`/`dangerFill` are the genuine computed
    values, not hand-typed stand-ins).

    @return `(engine, theme, merged)` -- the caller must keep `engine` AND
    `theme` alive for as long as any object it created is in use (a
    `QQmlPropertyMap` context property is only referenced, not owned, by
    the engine).
    """
    merged = with_token_defaults(palette if palette is not None else DISTINCT_PALETTE)
    engine = QQmlEngine()
    engine.addImportPath(str(PYSIDE_MVC_DIR))
    theme = QQmlPropertyMap()
    for key, value in merged.items():
        theme.insert(key, value)
    engine.rootContext().setContextProperty("Theme", theme)
    return engine, theme, merged


def collect_all_items(root):
    """@brief Every item in `root`'s visual subtree (`childItems()`,
    depth-first, `root` included), as one flat list the caller holds for as
    long as it needs any of them.

    @details Necessary, not just convenient, for a subtree containing a
    `Repeater`/`Loader`/`ListView` delegate: repeatedly calling
    `find_visual_child()` (a fresh recursive `childItems()` walk each time)
    was reproduced crashing with "Internal C++ object already deleted" on
    a *second* independent search over the same tree. A `Repeater`-managed
    item apparently is not attributable via `QObject.parent()` the way a
    statically-declared item is (the same break that defeats
    `findChild()`) — PySide's ownership rules then treat its transient,
    unreferenced Python wrapper as Python-owned, and garbage-collecting
    that wrapper after one search deletes the underlying, still-live,
    still-parented C++ item out from under the next search. Collecting
    every item ONCE into a list the test keeps alive for its own duration
    sidesteps the whole class of failure — nothing is ever wrapped and
    dropped again mid-test.
    """
    items = [root]
    for child in root.childItems():
        items.extend(collect_all_items(child))
    return items


def find_visual_child(item, object_name: str):
    """@brief Depth-first search over `childItems()` (the visual tree), not
    `QObject.findChild()` (the QObject-parent tree).

    @details Confirmed empirically for two unrelated components: a
    `ListView`'s `contentItem` and a plain `Repeater` (`AppRail`'s section
    rows, outside any `ListView`) both break the QObject parent chain
    `findChild()` needs — an item a `Repeater` instantiates is real, fully
    constructed, and visually present, yet unreachable from an ancestor via
    `findChild()` even long after creation. Once *inside* one repeated
    item's own statically-declared subtree, `findChild()` works normally
    again (Layout-wrapped or not) — this helper is only needed to cross a
    `Repeater`/`Loader`/`ListView`-delegate boundary, not for ordinary
    static QML nesting.

    @warning Safe for exactly ONE search over a tree containing a
    `Repeater`/`Loader`. A test needing to look up more than one such item
    must use `collect_all_items()` instead and keep the resulting list
    alive — see that function's own docstring for the crash this avoids.
    """
    if item.objectName() == object_name:
        return item
    for child in item.childItems():
        found = find_visual_child(child, object_name)
        if found is not None:
            return found
    return None


def load_qml_fixture(engine: QQmlEngine, fixture_path: Path):
    """@brief Loads `fixture_path` against `engine` and parents the result
    to `engine` before returning.

    @details A root object handed back by `QQmlComponent.create()` has no
    parent of its own — without one, once this function's local
    `component` goes out of scope and is garbage-collected, the underlying
    C++ item is destroyed with it ("Internal C++ object already deleted",
    reproduced empirically), even though the caller still holds a live
    Python reference to the returned object. Setting a real `QObject`
    parent hands ownership to Qt's own parent-child lifetime management
    instead of Python refcounting for `component`.
    """
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(fixture_path)))
    obj = component.create()
    assert component.errors() == [], component.errors()
    assert obj is not None
    obj.setParent(engine)
    return obj
