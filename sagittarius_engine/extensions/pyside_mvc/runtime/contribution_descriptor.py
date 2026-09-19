"""One shape for every contributed widget (`EPIC-001D` objective 2; `TASK-043`
E1).

An `IExtension` does not build UI and does not know where its widget ends up.
It hands the runtime a **descriptor**: who is contributing, to which surface,
in what place, roughly how big, and a factory that will build the widget
later. The runtime validates the descriptor immediately (`ContributionRegistry`)
and calls the factory only when the surface is first shown.

**`place` and `surface_id` are opaque `str`, not a closed `Enum` — this is the
one design choice this file exists to get right.** The runtime must not know
which places or surfaces a consuming application has (`EPIC-001D`'s own
design constraint: *"the runtime must not know the consuming application"*).
A consumer names its own closed vocabulary app-side (the reference consumer,
`Sagittarius_Elite_Warrior`, has its own `Place` — an `Enum` mixed with `str`
specifically so its members satisfy this file's `str` typing without the
runtime ever importing that `Enum`) and passes the concrete values through
these two fields. Harvested from that consumer's own `core/contracts/
contribution_descriptor.py`, once its `place` field was confirmed to already
be (or become) opaque-`str`-typed — verified, not assumed, by reading that
consumer's code before this file was written.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from sagittarius_engine.extensions.pyside_mvc.runtime.size_hint import SizeHint
from sagittarius_engine.interfaces.i_container import IContainer


@dataclass(frozen=True, slots=True)
class ContributionDescriptor:
    """A widget one `IExtension` offers to one place on one surface."""

    #: An app-defined contributor identity (a module id, or the app shell's
    #: own reserved id). Opaque to this runtime.
    contributor_id: str
    #: An app-defined surface identity, e.g. `"trading"`. Opaque to this
    #: runtime — `ContributionRegistry` validates it against the surfaces it
    #: was constructed with, not against any list this file knows about.
    surface_id: str
    #: An app-defined place identity, e.g. `"rail"`. Opaque to this runtime
    #: for the same reason as `surface_id`.
    place: str
    #: Sort key within `(surface_id, place)`. **Not** a uniqueness key: two
    #: independently written extensions may both pick 10 and still render in
    #: a stable order, rather than refusing to boot.
    order: int
    size_hint: SizeHint
    #: Builds the widget. Never called at contribute time.
    factory: Callable[[IContainer], QWidget]
    #: Free-form label a host may show (e.g. a rail entry's title or a
    #: settings section's heading). Meaning is entirely app-defined.
    title: str | None = None

    def identity(self) -> tuple[str, str, str, str]:
        """What may appear only once: this widget, in this place, from this
        contributor. Two different factories from one contributor in one
        place are two panels and are allowed."""
        return (
            self.surface_id,
            self.place,
            self.contributor_id,
            _factory_name(self.factory),
        )


def _factory_name(factory: Callable[..., object]) -> str:
    return getattr(factory, "__qualname__", repr(factory))
