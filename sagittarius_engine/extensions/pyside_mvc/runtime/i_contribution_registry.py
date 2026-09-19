"""What an `IExtension` may say at contribution time (`EPIC-001D` objective 2;
`TASK-043` E1).

The registry is the only thing an extension's contribution hook receives, so
this port is the whole surface area of "an extension adds UI": it takes a
descriptor and gives nothing back. An extension cannot enumerate another
extension's contributions, cannot reach a surface, and cannot build a widget
here — reading what was contributed is a host's job (`ContributionRegistry`
adds that side; see its own docstring).

Validation happens in this call, not at render time: an unknown surface, a
place the surface does not accept, or a duplicate identity raises
`ContributionError` while the stack still says which extension asked for it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sagittarius_engine.extensions.pyside_mvc.runtime.contribution_descriptor import (
    ContributionDescriptor,
)


@runtime_checkable
class IContributionRegistry(Protocol):
    """`Protocol` rather than `abc.ABC`: the sole implementation,
    `ContributionRegistry`, also implements the reading side this port does
    not declare, and a consumer wiring both through one object should not be
    forced into a second base class to satisfy this one."""

    def contribute(self, descriptor: ContributionDescriptor) -> None:
        """Offer one widget to one place. Raises `ContributionError` if the
        descriptor names a surface or place that cannot hold it, or repeats
        an identity already registered."""
        ...
