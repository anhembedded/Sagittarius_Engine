"""What a surface offers the widgets contributed to it (`EPIC-001D` objective
2; `TASK-043` E2).

Harvested from the reference consumer's own `IPlaceHost`
(`core/contracts/i_place_host.py`) — same three members, `place` opaque `str`
instead of that consumer's closed `Place` `Enum`, for the identical reason
`ContributionDescriptor.place` is opaque (see that file's own docstring).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


@runtime_checkable
class IRegionHost(Protocol):
    """`Protocol` rather than `abc.ABC`: the implementer is a `QMainWindow`
    subclass, and `ABCMeta` conflicts with Shiboken's metaclass — the same
    reason (a) `architecture-rule.md` §2.1 records for the reference
    consumer's own `IPlaceHost`, carried over verbatim since it is the same
    implementer shape here."""

    @property
    def surface_id(self) -> str:
        """The id contributions name. Opaque to this runtime."""
        ...

    def accepts(self) -> frozenset[str]:
        """The places this host can actually render. Opaque to this runtime."""
        ...

    def place_widget(
        self, place: str, widget: QWidget, *, title: str | None = None
    ) -> None:
        """Show `widget` in `place`. Called on the main thread only."""
        ...
