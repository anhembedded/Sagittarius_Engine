"""How much room a contributed widget wants (`EPIC-001D` objective 2;
`TASK-043` E1).

Three buckets, not pixels: the surface host owns the real geometry, and a
user's saved layout perspective overrides any hint. A module that needs an
exact size is describing a widget, not a contribution.

Harvested from the reference consumer's own `core/contracts/size_hint.py`
(`Sagittarius_Elite_Warrior`), verified stable and unchanged since that
consumer's `PR 0.2` (2026-09-11) through every phase since, per `TASK-043`'s
own harvest criterion (zero app imports, used by every one of that app's
bounded contexts, API unchanged for multiple phases).
"""

from __future__ import annotations

from enum import Enum


class SizeHint(Enum):
    #: A reading or a control strip — as little height as it can get.
    COMPACT = "compact"
    #: The default: a panel with content.
    REGULAR = "regular"
    #: Wants the full height of its dock area (a long list, a chart).
    TALL = "tall"
