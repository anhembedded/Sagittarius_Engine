"""What a surface will accept (`EPIC-001D` objective 2; `TASK-043` E1).

A **surface** is a place a user navigates to, described by an opaque id and
the set of opaque place identities it can hold. This is deliberately narrower
than the reference consumer's own `Surface` type (`core/contracts/surface.py`):
that type also carries `owner` and `gated_by`, both of which are that
consumer's own policy (who declares a surface; which config key gates it off
for a run) — `TASK-043` never asked for gating, and inventing it here ahead of
a second consumer needing it is exactly the premature generalization
`EPIC-001D`'s own "regions decide geometry, not policy" framing warns against.
An app that needs gating filters what it passes to `ContributionRegistry`
before calling `contribute()`, or keeps its own richer `Surface` type
app-side and derives a `SurfaceDeclaration` from it — either is a one-line
adapter, not a reason to widen this type.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SurfaceDeclaration:
    """One navigable surface, and what it will accept."""

    surface_id: str
    #: Checked at `contribute()` time: a contributor that offers a place a
    #: surface does not accept hears so immediately, not by finding its
    #: panel missing later.
    accepts: frozenset[str]
