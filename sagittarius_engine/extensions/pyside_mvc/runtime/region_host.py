"""A surface, rendered against real `QMainWindow` parts (`EPIC-001D`
objective 2; `TASK-043` E2).

Harvested from the reference consumer's own `WorkbenchSurface`
(`support/ui_kit/workbench_surface.py`), which has rendered every place on
every one of that app's six surfaces since `PR 1.4` (2026-09-11) with an
unchanged public shape through four phases — well past the harvest bar
(`TASK-043`'s own table: zero app imports, ≥2 consumers, API-stable a whole
phase). Two things changed to land here rather than a verbatim copy:

**`place` is an opaque `str`, not that consumer's closed `Place` `Enum`** —
the identical problem `ContributionDescriptor.place` solved in E1, solved the
same way. This class never imports or references that consumer's `Place`.

**Where a place physically renders is supplied by the caller, not hard-coded
here.** The reference consumer's own class dispatches on `Place.HEADER`,
`Place.RAIL`, etc. directly — a closed `if`/`elif` chain this runtime cannot
carry without importing that consumer's vocabulary. `RegionKind`
(`region_kind.py`) is what stays engine-owned instead — `QMainWindow`'s own,
genuinely universal anatomy — and the caller passes `place_regions`, a
mapping from each of its own opaque place identities to the `RegionKind` it
should occupy. The mapping is mandatory at construction, with no default:
the identical fix E1's `ContributionRegistry` already made to the one gap
the reference consumer's own registry still had (`surfaces` defaulting to a
global lookup) — this class never had that gap to begin with, so there is
nothing to fix, only a pattern to keep.

**Deliberately not harvested**: the reference consumer's environment-banner
slot (`WorkbenchSurface._environment_banner_factory`). It is already
zero-app-import as written, but it is shell chrome specific to that one
app's "which venue am I in" concern, not a place slot `TASK-043`'s own table
names — landing it here ahead of a second consumer asking for it is exactly
the premature generalization `EPIC-001D`'s own "regions decide geometry, not
policy" framing warns against (the same call `surface_declaration.py` made
for `Surface.owner`/`gated_by` in E1). A consumer that wants a banner row
keeps building it as its own `QToolBar` before handing widgets to this host,
or this class grows the slot when a second consumer needs the identical
shape.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QMainWindow,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from sagittarius_engine.extensions.pyside_mvc.runtime.contribution_error import (
    ContributionError,
)
from sagittarius_engine.extensions.pyside_mvc.runtime.region_kind import RegionKind
from sagittarius_engine.extensions.pyside_mvc.runtime.surface_declaration import (
    SurfaceDeclaration,
)

logger = logging.getLogger("App")

#: Bumped when a change to this class's own layout would make an older saved
#: blob apply wrongly rather than fail (a renamed dock, a removed toolbar).
#: `QMainWindow.restoreState` compares it and refuses a mismatch, which is
#: what turns "migrate or reset" into something the toolkit does for us.
PERSPECTIVE_VERSION = 1

_DOCK_AREA: dict[RegionKind, Qt.DockWidgetArea] = {
    RegionKind.DOCK_LEFT: Qt.DockWidgetArea.LeftDockWidgetArea,
    RegionKind.DOCK_RIGHT: Qt.DockWidgetArea.RightDockWidgetArea,
    RegionKind.DOCK_TOP: Qt.DockWidgetArea.TopDockWidgetArea,
    RegionKind.DOCK_BOTTOM: Qt.DockWidgetArea.BottomDockWidgetArea,
}


class RegionHost(QMainWindow):
    """One surface: a nested `QMainWindow` that renders contributed widgets.

    Satisfies `IRegionHost` **structurally**, with no base class — that port
    is a `Protocol` for the same reason as the reference consumer's own
    `IPlaceHost` (`i_region_host.py`'s own docstring).
    """

    def __init__(
        self,
        surface: SurfaceDeclaration,
        place_regions: Mapping[str, RegionKind],
        parent: QWidget | None = None,
    ) -> None:
        if frozenset(place_regions) != surface.accepts:
            raise ContributionError(
                f"surface {surface.surface_id!r} accepts "
                f"{sorted(surface.accepts)} but place_regions maps "
                f"{sorted(place_regions)} — every accepted place needs "
                "exactly one region, and place_regions may not name a place "
                "the surface does not accept."
            )
        super().__init__(parent)
        self._surface = surface
        self._place_regions = dict(place_regions)
        self._top_toolbar: QToolBar | None = None
        self._secondary_toolbar: QToolBar | None = None
        self._docks: dict[str, QDockWidget] = {}
        self._modals: dict[str, QDialog] = {}
        # A parent is not enough: `QMainWindow` sets the `Window` flag on
        # itself, so nested in a page or a stacked widget it would draw its
        # own title bar and frame. `Qt.WindowType.Widget` is `0`, so this
        # call *clears* the flag set — the documented way to un-window a
        # `QMainWindow`; without it `isWindow()` stays true even with a
        # parent (measured against the reference consumer's own `PR 1.4a`).
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setObjectName(f"surface::{surface.surface_id}")

    # -- IRegionHost (structural, no base class) ----------------------------

    @property
    def surface_id(self) -> str:
        return self._surface.surface_id

    def accepts(self) -> frozenset[str]:
        return self._surface.accepts

    def place_widget(
        self, place: str, widget: QWidget, *, title: str | None = None
    ) -> None:
        region = self._place_regions.get(place)
        if region is None:
            raise ContributionError(
                f"surface {self.surface_id!r} cannot render {place!r}; it "
                f"accepts {sorted(self._surface.accepts)}."
            )
        if region is RegionKind.TOP_TOOLBAR:
            self._toolbar_top().addWidget(widget)
        elif region is RegionKind.SECONDARY_TOOLBAR:
            self._toolbar_secondary().addWidget(widget)
        elif region is RegionKind.CENTRAL:
            self._set_central(widget)
        elif region in _DOCK_AREA:
            self._add_dock(place, region, widget, title)
        elif region is RegionKind.STATUS_BAR:
            self.statusBar().addPermanentWidget(widget)
        elif region is RegionKind.MODAL:
            self._keep_modal(place, widget, title)
        else:
            raise ContributionError(
                f"surface {self.surface_id!r} maps {place!r} to "
                f"{region!r}, which this host does not know how to "
                "render — a RegionKind was added without teaching this "
                "class about it."
            )

    # -- the perspective ------------------------------------------------

    def save_perspective(self) -> bytes:
        """This user's dock layout, for `restore_perspective()` to put back."""
        # Two steps: `saveState` answers a `QByteArray`, whose stubs declare
        # no `bytes()` overload, and whose `.data()` is typed
        # `bytes | bytearray | memoryview`. `bytes(...)` around *that*
        # narrows it.
        return bytes(self.saveState(PERSPECTIVE_VERSION).data())

    def restore_perspective(self, blob: bytes) -> bool:
        """Applies a saved layout. `False` (and a log line) when it does not
        apply, leaving the default layout standing — never an exception."""
        if not blob:
            return False
        if self.restoreState(blob, PERSPECTIVE_VERSION):
            return True
        logger.info(
            "Surface %r kept its default layout: the saved perspective "
            "does not apply (version %d, %d bytes).",
            self.surface_id,
            PERSPECTIVE_VERSION,
            len(blob),
        )
        return False

    # -- modals ------------------------------------------------------------

    def modal_titles(self) -> tuple[str, ...]:
        """Which dialogs this surface can raise, sorted, so a caller can
        build the actions that raise them without knowing what was
        contributed."""
        return tuple(sorted(self._modals))

    def show_modal(self, title: str) -> QDialog:
        """Raises the dialog contributed under `title`.

        Returns it rather than its result code: the caller decides `exec()`
        (modal) or `show()` (modeless), and a test wants the widget.
        """
        dialog = self._modals.get(title)
        if dialog is None:
            raise ContributionError(
                f"surface {self.surface_id!r} has no dialog titled "
                f"{title!r}; it has {list(self.modal_titles())}."
            )
        return dialog

    # -- the parts -----------------------------------------------------

    def _toolbar_top(self) -> QToolBar:
        if self._top_toolbar is None:
            self._top_toolbar = QToolBar("Top", self)
            self._top_toolbar.setObjectName(f"{self.objectName()}::top_toolbar")
            self._top_toolbar.setMovable(False)
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._top_toolbar)
        return self._top_toolbar

    def _toolbar_secondary(self) -> QToolBar:
        if self._secondary_toolbar is None:
            # Its own row under the top toolbar, not beside it.
            self._toolbar_top()
            self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
            self._secondary_toolbar = QToolBar("Secondary", self)
            self._secondary_toolbar.setObjectName(
                f"{self.objectName()}::secondary_toolbar"
            )
            self._secondary_toolbar.setMovable(False)
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._secondary_toolbar)
        return self._secondary_toolbar

    def _set_central(self, widget: QWidget) -> None:
        if self.centralWidget() is not None:
            raise ContributionError(
                f"surface {self.surface_id!r} already has a central "
                "widget. A surface has one subject; a second contribution "
                "to a CENTRAL region is two contributors each believing "
                "they own the centre."
            )
        self.setCentralWidget(widget)

    def _add_dock(
        self, place: str, region: RegionKind, widget: QWidget, title: str | None
    ) -> None:
        if not title:
            raise ContributionError(
                f"a {place!r} contributed to {self.surface_id!r} has no "
                "title. A dock the user can move, tab and close needs a "
                "name on it to find it again."
            )
        if title in self._docks:
            raise ContributionError(
                f"surface {self.surface_id!r} already has a panel titled "
                f"{title!r}. Two docks with one title are indistinguishable "
                "in a saved perspective."
            )
        dock = QDockWidget(title, self)
        # The object name is what `saveState()` keys a dock by — without it
        # the perspective silently fails to restore that panel.
        dock.setObjectName(f"{self.objectName()}::{place}::{title}")
        dock.setWidget(widget)
        area = _DOCK_AREA[region]
        self.addDockWidget(area, dock)
        previous = self._last_dock_in(area)
        if previous is not None:
            # Tab rather than stack: three panels stacked in one dock area
            # leave none of them readable, and the user can pull one out.
            self.tabifyDockWidget(previous, dock)
        self._docks[title] = dock

    def _last_dock_in(self, area: Qt.DockWidgetArea) -> QDockWidget | None:
        existing = [
            dock for dock in self._docks.values() if self.dockWidgetArea(dock) == area
        ]
        return existing[-1] if existing else None

    def _keep_modal(self, place: str, widget: QWidget, title: str | None) -> None:
        if not title:
            raise ContributionError(
                f"a modal contributed to {self.surface_id!r} ({place!r}) "
                "has no title. Every dialog's title names the action it "
                "performs."
            )
        if title in self._modals:
            raise ContributionError(
                f"surface {self.surface_id!r} already has a dialog titled {title!r}."
            )
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        self._modals[title] = dialog
