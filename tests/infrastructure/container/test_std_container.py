from __future__ import annotations

from abc import ABC, abstractmethod
from unittest.mock import patch

import pytest

from sagittarius_engine.exceptions import DependencyResolutionError
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.interfaces import IContainer


class IService:
    pass


class ConcreteService(IService):
    def __init__(self) -> None:
        self.value = 42


class ComplexService:
    def __init__(self, service: IService) -> None:
        self.service = service


class DefaultService:
    def __init__(self, service: IService, name: str = "default_name") -> None:
        self.service = service
        self.name = name


class MissingHintService:
    def __init__(self, service) -> None:
        pass


class AbstractService(ABC):
    @abstractmethod
    def run(self) -> None:
        pass


class CircularA:
    def __init__(self, b: "CircularB") -> None:
        pass


class CircularB:
    def __init__(self, a: "CircularA") -> None:
        pass


def test_bind_and_resolve_concrete():
    container = StdLibContainer()
    container.bind(IService, ConcreteService)

    instance1 = container.resolve(IService)
    instance2 = container.resolve(IService)

    assert isinstance(instance1, ConcreteService)
    assert isinstance(instance2, ConcreteService)
    assert instance1 is not instance2
    assert instance1.value == 42


def test_singleton_instance():
    container = StdLibContainer()
    service_instance = ConcreteService()
    container.singleton(IService, service_instance)

    instance1 = container.resolve(IService)
    instance2 = container.resolve(IService)

    assert instance1 is service_instance
    assert instance2 is service_instance


def test_singleton_factory():
    container = StdLibContainer()

    def factory(c: IContainer) -> ConcreteService:
        return ConcreteService()

    container.singleton(IService, factory)

    instance1 = container.resolve(IService)
    instance2 = container.resolve(IService)

    assert isinstance(instance1, ConcreteService)
    assert instance1 is instance2


def test_singleton_lazy_class():
    container = StdLibContainer()
    # It should automatically resolve dependencies of ConcreteService on first use
    container.singleton(IService, ConcreteService)

    instance1 = container.resolve(IService)
    instance2 = container.resolve(IService)

    assert isinstance(instance1, ConcreteService)
    assert instance1 is instance2


class FlakyService:
    """A class-registered singleton whose first construction attempt fails,
    simulating a dependency that is temporarily unavailable (TASK-017 issue 2)."""

    should_fail = True

    def __init__(self) -> None:
        if FlakyService.should_fail:
            raise RuntimeError("dependency temporarily unavailable")
        self.value = "ready"


def test_singleton_class_factory_survives_a_failed_resolve_and_retries():
    container = StdLibContainer()
    container.singleton(FlakyService, FlakyService)

    FlakyService.should_fail = True
    try:
        with pytest.raises(RuntimeError, match="dependency temporarily unavailable"):
            container.resolve(FlakyService)

        # Fixing the condition and retrying must still work — the failed
        # attempt must not have permanently dropped the registration.
        FlakyService.should_fail = False
        instance = container.resolve(FlakyService)
        assert instance.value == "ready"

        # The successful resolution is now cached as the singleton instance.
        assert container.resolve(FlakyService) is instance
    finally:
        FlakyService.should_fail = True


def test_resolve_with_dependencies():
    container = StdLibContainer()
    container.bind(IService, ConcreteService)
    # The container should auto-inject IService into ComplexService
    container.bind(ComplexService, ComplexService)

    complex_instance = container.resolve(ComplexService)

    assert isinstance(complex_instance, ComplexService)
    assert isinstance(complex_instance.service, ConcreteService)


def test_resolve_default_parameters():
    container = StdLibContainer()
    container.bind(IService, ConcreteService)

    instance = container.resolve(DefaultService)

    assert isinstance(instance, DefaultService)
    assert isinstance(instance.service, ConcreteService)
    # Note: StdLibContainer resolves str as str() == "" rather than falling back to default,
    # because it thinks it successfully instantiated a 'str'.
    assert instance.name == ""


def test_missing_type_hints_raises_error():
    container = StdLibContainer()
    with pytest.raises(DependencyResolutionError, match="Missing type hint"):
        container.resolve(MissingHintService)


def test_abstract_class_raises_error():
    container = StdLibContainer()
    with pytest.raises(
        DependencyResolutionError, match="Cannot instantiate abstract class"
    ):
        container.resolve(AbstractService)


def test_circular_dependency_raises_error():
    container = StdLibContainer()
    container.bind(CircularA, CircularA)
    container.bind(CircularB, CircularB)

    with pytest.raises(DependencyResolutionError, match="Circular dependency detected"):
        container.resolve(CircularA)


def test_unresolvable_dependency_without_default():
    container = StdLibContainer()

    class BrokenService:
        def __init__(self, something_unknown: AbstractService):
            pass

    with pytest.raises(DependencyResolutionError, match="Failed to resolve"):
        container.resolve(BrokenService)


def test_unresolvable_dependency_with_default():
    container = StdLibContainer()

    class ResilientService:
        def __init__(self, unknown: AbstractService = None):  # type: ignore
            self.unknown = unknown

    instance = container.resolve(ResilientService)
    assert instance.unknown is None


def test_not_a_class_raises_error():
    container = StdLibContainer()
    container.bind(IService, "not_a_class")  # type: ignore

    with pytest.raises(DependencyResolutionError, match="Cannot resolve"):
        container.resolve(IService)


def test_resolve_caching():
    # Test that the cache works correctly across multiple instantiations
    container = StdLibContainer()
    container.bind(IService, ConcreteService)
    container.bind(ComplexService, ComplexService)

    # First resolve builds the cache
    first_instance = container.resolve(ComplexService)
    # Second resolve uses the cache
    second_instance = container.resolve(ComplexService)

    assert isinstance(first_instance, ComplexService)
    assert isinstance(second_instance, ComplexService)
    assert first_instance is not second_instance


def test_resolve_value_error_signature():
    container = StdLibContainer()

    # Trying to resolve something without signature
    # (builtins generally have no python signature)
    # but we can mock it
    class MockNoSig:
        pass

    with patch("inspect.signature", side_effect=ValueError):
        instance = container.resolve(MockNoSig)
        assert isinstance(instance, MockNoSig)


def test_resolve_type_hints_exception():
    container = StdLibContainer()

    class WeirdHintsService:
        def __init__(self, weird):
            pass

    with patch("typing.get_type_hints", side_effect=Exception):
        with pytest.raises(DependencyResolutionError, match="Missing type hint"):
            container.resolve(WeirdHintsService)


def test_type_hint_parameter_empty():
    container = StdLibContainer()

    class MissingHintService2:
        def __init__(self, missing):
            pass

    with pytest.raises(DependencyResolutionError, match="Missing type hint"):
        container.resolve(MissingHintService2)


def test_kwarg_args_self_ignored():
    container = StdLibContainer()

    class IgnoreArgsService:
        def __init__(self, *args, **kwargs):
            pass

    instance = container.resolve(IgnoreArgsService)
    assert isinstance(instance, IgnoreArgsService)
