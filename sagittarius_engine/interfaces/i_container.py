from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

T = TypeVar("T", bound=Any)

Lifetime = Literal["singleton", "transient", "scoped"]


@dataclass(frozen=True)
class Registration:
    """
    @brief One entry in a container's registry — what `registrations()` reports.

    @details A read-only description of a registration, never a handle to the
    instance itself: a diagnostic that resolves things in order to describe
    them would construct half the application as a side effect of being asked
    a question.

    @param abstract The type callers pass to `resolve()`.
    @param concrete The type that will be constructed, where the container
        knows it. `None` for a singleton registered as a factory or lambda,
        whose result type is unknowable before it runs.
    @param lifetime `"singleton"`, `"transient"` or `"scoped"`.
    @param instantiated Whether an instance already exists. `False` for a
        singleton that has been registered but never resolved — the
        distinction matters when the question is "what has actually been
        built so far".
    """

    abstract: type
    concrete: type | None
    lifetime: Lifetime
    instantiated: bool


class IContainer(ABC):
    """
    @brief Interface for the Dependency Injection Container.

    @details The Container manages the initialization and distribution of dependencies.
    Instead of manually instantiating classes (e.g., new ClassA()), the Container
    automatically resolves them.

    @par Tutorial / Usage Example:
    @code
    container = StdLibContainer()
    container.bind(IUserRepository, PostgresUserRepository)

    # Get an instance (Dependencies are automatically resolved if any)
    repo = container.resolve(IUserRepository)
    @endcode
    """

    @abstractmethod
    def bind(self, abstract: type[Any], concrete: type[Any]) -> None:
        """
        @brief Binds an Interface to a specific Implementation.
        @details A new instance is created every time it is resolved (Transient).

        @param abstract The interface or abstract class type.
        @param concrete The concrete class type to instantiate.
        """
        ...

    @abstractmethod
    def singleton(
        self,
        abstract: type[Any],
        instance_or_factory: Any,
    ) -> None:
        """
        @brief Registers a Singleton.
        @details The instance is created once and reused for all subsequent resolve requests.

        @param abstract The interface or abstract class type.
        @param instance_or_factory The existing instance or a factory function.
        """
        ...

    @abstractmethod
    def resolve(self, abstract: type[Any]) -> Any:
        """
        @brief Resolves and returns an instance of the requested type.

        @param abstract The class type to resolve.
        @return An instance of the requested type.
        """
        ...

    @abstractmethod
    def scoped(self, abstract: type[Any], concrete: type[Any]) -> None:
        """
        @brief Registers a Scoped dependency.

        @details A scoped instance is created once per active scope (e.g., per HTTP request).
        Within the same scope, the same instance is returned. Different scopes receive
        different instances. If no scope is active, resolving a scoped dependency raises
        a DependencyResolutionError.

        @param abstract The abstract interface or class type.
        @param concrete The concrete class to instantiate within each scope.
        """
        ...

    @abstractmethod
    def create_scope(self) -> Any:
        """
        @brief Creates and returns a new dependency scope context manager.

        @details Use this as a context manager to define the boundary of a scope:

        @code
        with container.create_scope():
            session = container.resolve(ISession)  # scoped to this block
        @endcode

        @return A context manager (ScopeContext) that activates and deactivates the scope.
        """
        ...

    def registrations(self) -> Mapping[type, Registration]:
        """
        @brief Everything currently registered, keyed by the abstract type.

        @details `resolve()` answers "give me a T" for a T the caller already
        names. This answers "what have you got", which is what a caller needs
        in order to check registrations it was never told about — that every
        binding is constructible, that nothing was registered twice under
        conflicting lifetimes, that a handler's dependency is actually
        satisfiable before a user triggers it rather than after (`EPIC-006`).

        @return Abstract type -> `Registration`. Where the same abstract is
        registered more than once, the entry reports the lifetime `resolve()`
        would actually use, not every registration made. The mapping is a
        snapshot and never triggers construction.

        @par Why this is concrete rather than abstract
        Same reason as `IEventBus.subscriptions()`: an `IContainer` implemented
        outside this repository keeps working. A default of empty is
        indistinguishable from a container with nothing registered, so a caller
        that must tell those apart can check whether it was overridden:

        @code
        introspectable = type(c).registrations is not IContainer.registrations
        @endcode

        `StdLibContainer` overrides it, and
        `tests/test_architecture.py::test_containers_implement_registrations`
        fails if a new container does not.
        """
        return {}

    def open_scope_count(self) -> int:
        """
        @brief How many `create_scope()` blocks are currently entered — `EPIC-007B`.

        @details A count that only rises across successive reads is a leaked scope —
        something entered a `with create_scope():` block and never exited it,
        invisible by any other means today.

        @par Why this is concrete rather than abstract
        Same reasoning as `registrations()`: an `IContainer` implemented outside this
        repository keeps working. `0` here is genuinely ambiguous between "nothing is
        open" and "not tracked" — the same ambiguity `registrations()`'s own docstring
        names for an empty mapping — and is accepted for the same reason: consistency
        with the one escape hatch already established, rather than a second, differently
        shaped one for this method alone.
        """
        return 0
