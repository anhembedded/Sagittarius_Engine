"""The runtime's side of the contribution mechanism (`EPIC-001D` objective 2;
`TASK-043` E1).

Validates and stores what every `IExtension` contributed this run: `contribute()`
is what `IContributionRegistry` declares; `panels()`/`surface_declaration()` are
the reading side a surface host uses to render. One object behind both, the
same shape the reference consumer's own `ContributionRegistry` already proved
(`Sagittarius_Elite_Warrior`, `shell/contribution_registry.py`) — kept as one
class here too rather than split into a write/read `Protocol` pair, since
nothing has yet needed to hand out only the read half; that split is a
one-class-to-two-files change when a second consumer does.

**Order is a sort key, not an identity.** Rendering order is the stable sort
by `(order, contributor_id, factory qualname)`, so two independently written
extensions that both pick `order = 10` render in a fixed order rather than
refusing to boot. What may not repeat is `(surface_id, place, contributor_id,
factory)`.

**This runtime does not know which surfaces or places exist.** The caller
supplies every `SurfaceDeclaration` at construction; there is no default and
no fallback to a global lookup — the one place the reference consumer's own
registry still had that gap (`ContributionRegistry.__init__`'s `surfaces`
parameter defaulting to its own `surfaces_by_id()`), left as a note for that
consumer's own migration rather than copied here.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from sagittarius_engine.extensions.pyside_mvc.runtime.contribution_descriptor import (
    ContributionDescriptor,
)
from sagittarius_engine.extensions.pyside_mvc.runtime.contribution_error import (
    ContributionError,
)
from sagittarius_engine.extensions.pyside_mvc.runtime.surface_declaration import (
    SurfaceDeclaration,
)

logger = logging.getLogger("App")


class ContributionRegistry:
    def __init__(self, surfaces: Iterable[SurfaceDeclaration]) -> None:
        self._surfaces = {surface.surface_id: surface for surface in surfaces}
        self._panels: list[ContributionDescriptor] = []
        self._identities: set[tuple[str, str, str, str]] = set()

    # -- the extension-facing side (IContributionRegistry) -----------------

    def contribute(self, descriptor: ContributionDescriptor) -> None:
        surface = self._surfaces.get(descriptor.surface_id)
        if surface is None:
            raise ContributionError(
                f"{descriptor.contributor_id!r} contributed {descriptor.place!r} "
                f"to the unknown surface {descriptor.surface_id!r}. Known "
                f"surfaces: {sorted(self._surfaces)}."
            )
        if descriptor.place not in surface.accepts:
            raise ContributionError(
                f"surface {surface.surface_id!r} does not accept "
                f"{descriptor.place!r} (asked for by {descriptor.contributor_id!r}); "
                f"it accepts {sorted(surface.accepts)}."
            )

        identity = descriptor.identity()
        if identity in self._identities:
            raise ContributionError(
                f"{descriptor.contributor_id!r} contributed the same factory to "
                f"{descriptor.surface_id!r}/{descriptor.place!r} twice."
            )
        self._identities.add(identity)
        self._panels.append(descriptor)

    # -- the host-facing side ------------------------------------------------

    def surface_declaration(self, surface_id: str) -> SurfaceDeclaration:
        """The surface declaration behind an id.

        The registry validates every contribution against this same table, so
        it is the one object that already knows both halves a host needs.
        """
        surface = self._surfaces.get(surface_id)
        if surface is None:
            raise ContributionError(
                f"no surface is declared with the id {surface_id!r}. Known "
                f"surfaces: {sorted(self._surfaces)}."
            )
        return surface

    def panels(self, surface_id: str, place: str) -> tuple[ContributionDescriptor, ...]:
        """Everything contributed to one place, in render order."""
        matching = [
            descriptor
            for descriptor in self._panels
            if descriptor.surface_id == surface_id and descriptor.place == place
        ]
        return tuple(sorted(matching, key=_render_key))


def _render_key(descriptor: ContributionDescriptor) -> tuple[int, str, str]:
    factory_name = getattr(descriptor.factory, "__qualname__", repr(descriptor.factory))
    return (descriptor.order, descriptor.contributor_id, factory_name)
