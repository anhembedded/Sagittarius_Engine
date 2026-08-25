"""`IContainer.registrations()` — the enumeration half of the container.

`resolve(T)` answers only for a `T` the caller already names. `EPIC-006` needs
the opposite direction: what is registered, so that every binding can be checked
for constructibility *before* a user triggers the command that needs it.

The lazy-singleton lifecycle is the case worth pinning. `singleton(abstract,
SomeClass)` installs a factory; on first resolve that factory pops itself and
the built object lands in `_instances`. The registration is a singleton in both
states and only `instantiated` separates them.
"""

import pytest

from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.interfaces import IContainer


class IService:
    pass


class Service(IService):
    pass


class Other:
    pass


def test_bind_is_reported_as_transient_and_not_instantiated():
    c = StdLibContainer()
    c.bind(IService, Service)

    reg = c.registrations()[IService]

    assert reg.abstract is IService
    assert reg.concrete is Service
    assert reg.lifetime == "transient"
    assert reg.instantiated is False


def test_resolving_a_transient_does_not_mark_it_instantiated():
    c = StdLibContainer()
    c.bind(IService, Service)
    c.resolve(IService)

    assert c.registrations()[IService].instantiated is False, (
        "a transient builds a new object every time; there is no single "
        "instance for the registry to describe"
    )


def test_a_registered_instance_is_a_live_singleton():
    c = StdLibContainer()
    instance = Service()
    c.singleton(IService, instance)

    reg = c.registrations()[IService]

    assert reg.lifetime == "singleton"
    assert reg.instantiated is True
    assert reg.concrete is Service


def test_lazy_singleton_before_and_after_first_resolve():
    c = StdLibContainer()
    c.singleton(IService, Service)

    before = c.registrations()[IService]
    assert before.lifetime == "singleton"
    assert before.instantiated is False
    assert before.concrete is None, (
        "a factory's result type is unknowable until it runs, and running it "
        "to answer this question would build the object as a side effect"
    )

    c.resolve(IService)

    after = c.registrations()[IService]
    assert after.lifetime == "singleton", (
        "the factory pops itself on first resolve; if registrations() read "
        "only _factories the registration would vanish here"
    )
    assert after.instantiated is True
    assert after.concrete is Service


def test_a_factory_lambda_is_reported_without_being_called():
    called = []
    c = StdLibContainer()
    c.singleton(IService, lambda _c: called.append(1) or Service())

    reg = c.registrations()[IService]

    assert reg.lifetime == "singleton"
    assert reg.instantiated is False
    assert called == [], "describing a registration must not construct it"


def test_scoped_registration_is_reported():
    c = StdLibContainer()
    c.scoped(IService, Service)

    reg = c.registrations()[IService]

    assert reg.lifetime == "scoped"
    assert reg.concrete is Service
    assert reg.instantiated is False


def test_reports_the_lifetime_resolve_would_actually_use():
    """Precedence in `resolve()` is scoped > instance > factory > binding."""
    c = StdLibContainer()
    c.bind(IService, Service)
    c.singleton(IService, Service())

    assert c.registrations()[IService].lifetime == "singleton"

    c.scoped(IService, Service)

    assert c.registrations()[IService].lifetime == "scoped"


def test_reports_every_abstract_registered():
    c = StdLibContainer()
    c.bind(IService, Service)
    c.singleton(Other, Other())

    assert set(c.registrations()) == {IService, Other}


def test_result_is_a_snapshot_not_a_live_view():
    c = StdLibContainer()
    c.bind(IService, Service)

    snapshot = c.registrations()
    c.bind(Other, Other)

    assert Other not in snapshot


def test_an_empty_container_reports_nothing():
    assert StdLibContainer().registrations() == {}


def test_the_interface_default_is_empty_so_a_foreign_container_still_works():
    """`code-rule.md` §L forbids the NotImplementedError alternative."""

    class ForeignContainer(IContainer):
        def bind(self, abstract, concrete): ...
        def singleton(self, abstract, instance_or_factory): ...
        def resolve(self, abstract): ...
        def scoped(self, abstract, concrete): ...
        def create_scope(self): ...

    assert ForeignContainer().registrations() == {}


def test_registration_is_immutable():
    c = StdLibContainer()
    c.bind(IService, Service)
    reg = c.registrations()[IService]

    with pytest.raises(Exception):
        reg.lifetime = "scoped"  # type: ignore[misc]
