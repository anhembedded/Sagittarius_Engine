import inspect
import threading
from collections.abc import Callable
from typing import Any, TypeVar

from sagittarius_engine.exceptions import DependencyResolutionError
from sagittarius_engine.infrastructure.container.scope_context import ScopeContext
from sagittarius_engine.interfaces import IContainer

T = TypeVar("T")


class StdLibContainer(IContainer):
    """
    @brief Dependency Injection Container using the Python Standard Library (`inspect`).

    @details Responsible for automatically resolving dependencies for classes.
    The Container reads Type Hints (Type Annotations) in the `__init__` method to know
    what dependencies a class requires, then automatically instantiates and injects them.

    @par Tutorial / Usage Example:
    @code
    container = StdLibContainer()

    # 1. Register a Singleton (A single shared instance)
    container.singleton(IEventBus, MemoryEventBus())

    # 2. Register a standard Binding (A new instance is created on each resolve)
    container.bind(IUserRepository, PostgresUserRepository)

    # 3. Use a factory function if initialization is complex
    def make_db(container):
        return DatabaseConnection(host="localhost")
    container.singleton(DatabaseConnection, make_db)

    # 4. Resolve (Automatic dependency injection)
    # If CommandA requires IUserRepository in __init__, the container will
    # automatically fetch PostgresUserRepository and pass it in.
    command = container.resolve(CommandA)
    @endcode
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._bindings: dict[type, type] = {}
        self._instances: dict[type, Any] = {}
        self._factories: dict[type, Callable] = {}
        self._scoped_registry: dict[type, type] = {}
        self._scope_context: ScopeContext = ScopeContext(self._scoped_registry)
        # Cache for parsed __init__ dependencies to speed up resolution
        self._resolution_cache: dict[type, dict[str, dict[str, Any]]] = {}

    def bind(self, abstract: type, concrete: type) -> None:
        """
        @brief Registers a mapping between an Interface and a concrete Class (Transient).

        @param abstract The abstract interface or class.
        @param concrete The concrete class to bind.
        """
        with self._lock:
            self._bindings[abstract] = concrete

    def singleton(self, abstract: type, instance_or_factory: Any | Callable) -> None:
        """
        @brief Registers an existing instance, a class, or a Factory function (executed once).

        @param abstract The abstract interface or class.
        @param instance_or_factory
            - A **concrete instance** (e.g. ``MemoryEventBus()``): stored as-is.
            - A **class** (e.g. ``SqliteStudentRepository``): treated as a lazy factory;
              the container resolves it (with auto-injection) on first use.
            - A **callable/lambda** (e.g. ``lambda c: c.resolve(X)``): called once on
              first use; the result is cached as the singleton.
        """
        with self._lock:
            if isinstance(instance_or_factory, type):
                # Class passed — wrap in a lazy factory so the container can
                # auto-inject all constructor dependencies on first resolve.
                # This allows: singleton(IRepo, ConcreteRepo)
                # instead of:  singleton(IRepo, lambda c: c.resolve(ConcreteRepo))
                concrete = instance_or_factory

                def _lazy_factory(c, _abstract=abstract, _cls=concrete):
                    # Pop ourselves FIRST to break the cycle when abstract == concrete.
                    # After this factory returns, the caller (_resolve) will store the
                    # result in _instances, so the factory is never invoked again.
                    c._factories.pop(_abstract, None)
                    return c._resolve(_cls, set())

                self._factories[abstract] = _lazy_factory
            elif callable(instance_or_factory):
                # Factory function / lambda — call once and cache the result.
                self._factories[abstract] = instance_or_factory
            else:
                # Concrete instance — store directly.
                self._instances[abstract] = instance_or_factory

    def resolve(self, abstract: type[Any]) -> Any:
        """
        @brief Resolves and retrieves an instance of the requested type.
        @details This function recursively resolves the entire dependency tree.

        @param abstract The class type to resolve.
        @return An instance of the requested type.
        @exception DependencyResolutionError If the container cannot resolve a dependency.
        """
        # Check scoped registry first
        scoped_instance = self._scope_context.resolve(abstract)
        if scoped_instance is not None:
            return scoped_instance
        return self._resolve(abstract, set())

    def scoped(self, abstract: type[Any], concrete: type[Any]) -> None:
        """
        @brief Registers a Scoped dependency.

        @details A scoped instance is created once per active scope (e.g., per HTTP request).
        Different scopes receive different instances; same scope reuses one instance.
        Resolving a scoped dependency outside an active scope falls back to Transient.

        @param abstract The abstract interface or class type.
        @param concrete The concrete class to instantiate within each scope.
        """
        with self._lock:
            self._scoped_registry[abstract] = concrete

    def create_scope(self) -> ScopeContext:
        """
        @brief Creates a new scope context manager.

        @details Use as a context manager to isolate scoped dependency resolution:

            with container.create_scope():
                session = container.resolve(ISession)  # scoped instance
                # same session returned within this block
            # scope is released; next create_scope() produces a fresh set

        @return A ScopeContext that activates a new isolated resolution scope.
        """
        return ScopeContext(self._scoped_registry)

    def _resolve(self, abstract: type[T] | Any, resolving: set[type]) -> T:  # noqa: C901
        """
        @brief Internal recursive resolve method with circular dependency detection.
        """
        # CPython dictionary gets are atomic and GIL-protected. Lock-free read.
        if abstract in self._instances:
            return self._instances[abstract]

        # Lock-free read for factories to reduce contention
        factory = self._factories.get(abstract)
        if factory is not None:
            with self._lock:
                # Double-checked locking
                if abstract in self._instances:
                    return self._instances[abstract]
                if abstract in self._factories:
                    instance = self._factories[abstract](self)
                    self._instances[abstract] = instance
                    return instance

        concrete = self._bindings.get(abstract, abstract)

        if concrete in resolving:
            raise DependencyResolutionError(f"Circular dependency detected: {concrete}")

        if not inspect.isclass(concrete):
            raise DependencyResolutionError(f"Cannot resolve {abstract}")

        if getattr(concrete, "__abstractmethods__", None):
            raise DependencyResolutionError(
                f"Cannot instantiate abstract class {concrete}"
            )

        resolving.add(concrete)

        try:
            if getattr(concrete, "__init__", None) is object.__init__:
                return concrete()

            # Check cache first to avoid slow inspect.signature and get_type_hints calls
            # CPython dictionary gets are atomic and GIL-protected. Lock-free read.
            cached_deps = self._resolution_cache.get(concrete)

            if cached_deps is None:
                try:
                    signature = inspect.signature(concrete.__init__)
                except ValueError:
                    with self._lock:
                        self._resolution_cache[concrete] = {}
                    return concrete()

                import typing

                try:
                    type_hints = typing.get_type_hints(concrete.__init__)
                except Exception:
                    type_hints = None

                cached_deps = {}
                for name, param in signature.parameters.items():
                    if name in ("self", "args", "kwargs"):
                        continue

                    annotation = inspect.Parameter.empty
                    if type_hints is not None and name in type_hints:
                        annotation = type_hints[name]
                    else:
                        annotation = param.annotation

                    if annotation == inspect.Parameter.empty:
                        raise DependencyResolutionError(
                            f"Missing type hint for parameter '{name}' in {concrete.__name__}"
                        )

                    cached_deps[name] = {
                        "annotation": annotation,
                        "has_default": param.default is not inspect.Parameter.empty,
                        "default": param.default,
                    }

                with self._lock:
                    self._resolution_cache[concrete] = cached_deps

            dependencies = {}
            for name, param_info in cached_deps.items():
                try:
                    dependencies[name] = self._resolve(
                        param_info["annotation"], resolving
                    )
                except Exception as e:
                    if param_info["has_default"]:
                        dependencies[name] = param_info["default"]
                    else:
                        raise DependencyResolutionError(
                            f"Failed to resolve '{name}' for {concrete.__name__}: {str(e)}"
                        )

            return concrete(**dependencies)
        finally:
            resolving.remove(concrete)
