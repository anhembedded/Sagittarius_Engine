from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

_current_scope: ContextVar[dict[type, Any] | None] = ContextVar(
    "_current_scope", default=None
)


class ScopeContext:
    """
    @brief Context manager that creates an isolated dependency resolution scope.

    @details Within the scope, all `scoped` registrations resolve to the same instance.
    Different scopes (e.g., different HTTP requests) receive different instances.

    Usage:
        with container.create_scope():
            session1 = container.resolve(ISession)  # new scoped instance
            session2 = container.resolve(ISession)  # same instance as session1

        with container.create_scope():
            session3 = container.resolve(ISession)  # brand-new instance
    """

    def __init__(
        self,
        scoped_registry: dict[type, type],
        *,
        on_enter: Callable[[], None] | None = None,
        on_exit: Callable[[], None] | None = None,
    ) -> None:
        """
        @param on_enter, on_exit `EPIC-007B`: hooks a container's own open-scope
            census onto this scope's real lifetime, `__enter__`/`__exit__` — not the
            moment `create_scope()` constructs the object, which can happen without the
            `with` block that actually activates it ever running. `None` by default:
            `StdLibContainer`'s own `self._scope_context` (used only for `resolve()`
            lookups, never entered as a `with` block) must not be counted as an open
            scope just because it exists.
        """
        self._scoped_registry = scoped_registry
        self._token: Any = None
        self._on_enter = on_enter
        self._on_exit = on_exit

    def __enter__(self) -> "ScopeContext":
        self._token = _current_scope.set({})
        if self._on_enter is not None:
            self._on_enter()
        return self

    def __exit__(self, *args: object) -> None:
        _current_scope.reset(self._token)
        if self._on_exit is not None:
            self._on_exit()

    def resolve(self, abstract: type) -> Any | None:
        """
        @brief Resolves a scoped instance within the current scope.
        @return Instance if abstract is scoped and a scope is active, else None.
        """
        scope = _current_scope.get()
        if scope is None:
            return None

        concrete = self._scoped_registry.get(abstract)
        if concrete is None:
            return None

        if abstract not in scope:
            scope[abstract] = concrete()

        return scope[abstract]
