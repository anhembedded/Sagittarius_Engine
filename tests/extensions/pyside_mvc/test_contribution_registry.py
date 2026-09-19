"""Behavior tests for the contribution mechanism (`EPIC-001D` objective 2;
`TASK-043` E1): `ContributionDescriptor.identity()`, `ContributionRegistry`'s
three `contribute()` raise paths plus its success path, `panels()`'s stable
render order, and `surface_declaration()`'s raise path.
"""

from __future__ import annotations

import pytest

from sagittarius_engine.extensions.pyside_mvc.runtime import (
    ContributionDescriptor,
    ContributionError,
    ContributionRegistry,
    SizeHint,
    SurfaceDeclaration,
)


def _descriptor(
    *,
    contributor_id: str = "market_data",
    surface_id: str = "trading",
    place: str = "rail",
    order: int = 10,
    factory=lambda container: None,
    title: str | None = None,
) -> ContributionDescriptor:
    return ContributionDescriptor(
        contributor_id=contributor_id,
        surface_id=surface_id,
        place=place,
        order=order,
        size_hint=SizeHint.REGULAR,
        factory=factory,
        title=title,
    )


def _registry(**surfaces: frozenset[str]) -> ContributionRegistry:
    declarations = [
        SurfaceDeclaration(surface_id=surface_id, accepts=accepts)
        for surface_id, accepts in surfaces.items()
    ]
    return ContributionRegistry(declarations)


def test_identity_is_the_surface_place_contributor_and_factory_qualname() -> None:
    def build(container: object) -> None:
        return None

    descriptor = _descriptor(factory=build)

    assert descriptor.identity() == (
        "trading",
        "rail",
        "market_data",
        build.__qualname__,
    )


def test_two_factories_from_one_contributor_in_one_place_have_different_identities() -> (
    None
):
    def first(container: object) -> None:
        return None

    def second(container: object) -> None:
        return None

    a = _descriptor(factory=first)
    b = _descriptor(factory=second)

    assert a.identity() != b.identity()


def test_contribute_to_an_unknown_surface_raises() -> None:
    registry = _registry(trading=frozenset({"rail"}))

    with pytest.raises(ContributionError, match="unknown surface"):
        registry.contribute(_descriptor(surface_id="dashboard"))


def test_contribute_a_place_the_surface_does_not_accept_raises() -> None:
    registry = _registry(trading=frozenset({"rail"}))

    with pytest.raises(ContributionError, match="does not accept"):
        registry.contribute(_descriptor(place="console"))


def test_contribute_the_same_identity_twice_raises() -> None:
    registry = _registry(trading=frozenset({"rail"}))
    registry.contribute(_descriptor())

    with pytest.raises(ContributionError, match="twice"):
        registry.contribute(_descriptor())


def test_contribute_accepts_a_declared_place_and_the_panel_is_readable() -> None:
    registry = _registry(trading=frozenset({"rail"}))
    descriptor = _descriptor()

    registry.contribute(descriptor)

    assert registry.panels("trading", "rail") == (descriptor,)


def test_panels_render_order_is_order_then_contributor_id_then_factory_name() -> None:
    registry = _registry(trading=frozenset({"rail"}))

    def factory_a(container: object) -> None:
        return None

    def factory_b(container: object) -> None:
        return None

    later_order = _descriptor(contributor_id="strategy", order=20, factory=factory_a)
    tied_order_first_by_contributor = _descriptor(
        contributor_id="market_data", order=10, factory=factory_a
    )
    tied_order_second_by_contributor = _descriptor(
        contributor_id="strategy", order=10, factory=factory_b
    )
    registry.contribute(later_order)
    registry.contribute(tied_order_second_by_contributor)
    registry.contribute(tied_order_first_by_contributor)

    assert registry.panels("trading", "rail") == (
        tied_order_first_by_contributor,
        tied_order_second_by_contributor,
        later_order,
    )


def test_panels_only_returns_matches_for_the_requested_surface_and_place() -> None:
    registry = _registry(trading=frozenset({"rail", "console"}))
    rail = _descriptor(place="rail")
    console = _descriptor(place="console", factory=lambda container: None)
    registry.contribute(rail)
    registry.contribute(console)

    assert registry.panels("trading", "rail") == (rail,)


def test_panels_for_an_unknown_place_is_empty() -> None:
    registry = _registry(trading=frozenset({"rail"}))

    assert registry.panels("trading", "console") == ()


def test_surface_declaration_returns_the_declared_surface() -> None:
    declaration = SurfaceDeclaration(surface_id="trading", accepts=frozenset({"rail"}))
    registry = ContributionRegistry([declaration])

    assert registry.surface_declaration("trading") is declaration


def test_surface_declaration_for_an_unknown_id_raises() -> None:
    registry = _registry(trading=frozenset({"rail"}))

    with pytest.raises(ContributionError, match="no surface is declared"):
        registry.surface_declaration("dashboard")
