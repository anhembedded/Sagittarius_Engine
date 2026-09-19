"""Where a `RegionHost` can physically put a widget (`EPIC-001D` objective 2;
`TASK-043` E2).

Unlike `place` on `ContributionDescriptor` (an app-defined, opaque identity —
`contribution_descriptor.py`'s own docstring explains why), `RegionKind` is a
**closed, engine-owned** vocabulary: it names `QMainWindow`'s own anatomy, not
anything an application invents. A `QMainWindow` has exactly these regions
regardless of which app is running, the same way `SizeHint`'s three buckets
are a universal layout concept rather than app policy — this is that same
kind of harvest call, made explicitly rather than assumed (`TASK-043`'s own
E1 note on `SizeHint` flagged the two as needing separate judgment).

`RegionHost` never sees an app's own place names (`"rail"`, `"header"`, ...)
as anything but opaque strings — the app supplies the mapping from each of
its own places to a `RegionKind` at construction. This is the harvest of the
same problem `Place` posed in E1, solved the same way one level up: the
opaque identity a `ContributionDescriptor` carries is app policy; *how many
kinds of physical regions a window has* is not.
"""

from __future__ import annotations

from enum import Enum


class RegionKind(Enum):
    #: The window's primary, topmost toolbar row.
    TOP_TOOLBAR = "top_toolbar"
    #: A second toolbar row, directly under the first.
    SECONDARY_TOOLBAR = "secondary_toolbar"
    #: The window's one central widget.
    CENTRAL = "central"
    #: A dock in the left dock area.
    DOCK_LEFT = "dock_left"
    #: A dock in the right dock area.
    DOCK_RIGHT = "dock_right"
    #: A dock in the top dock area.
    DOCK_TOP = "dock_top"
    #: A dock in the bottom dock area.
    DOCK_BOTTOM = "dock_bottom"
    #: A permanent widget in the status bar.
    STATUS_BAR = "status_bar"
    #: Not placed in the layout at all — kept as a dialog the host can raise.
    MODAL = "modal"
