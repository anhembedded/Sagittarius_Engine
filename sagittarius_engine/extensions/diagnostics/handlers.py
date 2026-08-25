"""Finding the dispatchable handlers in a running application — `EPIC-006D`.

`Dispatcher.dispatch(handler_class, dto)` resolves the handler class straight
from the container. There is no registration step, so a handler appears in no
registry the engine keeps: not in `IContainer.registrations()` (nothing binds
it), and not in a subclass registry either.

`EPIC-006D`'s spec recommended discovering handlers through
`__init_subclass__` on `IDispatchable`, following the pattern
`BaseEvent`/`EventRegistry` already uses successfully here. **Measured, that
does not work.** `IDispatchable` is a duck-typed marker, not an ABC and not a
`typing.Protocol`, and its own docstring says so: *"Any handler class that
implements `execute(dto) -> TResult` is considered dispatchable."* The engine's
reference application takes it at its word — every one of
`examples/student_management`'s handlers is a bare `class XHandler:` inheriting
nothing at all. A subclass registry would have found **zero** of them.

So discovery is structural, matching how dispatch itself works.
"""

from __future__ import annotations

import inspect
import sys
from collections.abc import Iterable

#: Classes that satisfy the structural test but *are* the marker interfaces
#: rather than handlers written against them. Excluded by identity rather than
#: by a name pattern, so renaming one cannot silently re-admit it.
_INTERFACE_NAMES = frozenset(
    {
        "sagittarius_engine.interfaces.i_dispatchable.IDispatchable",
        "sagittarius_engine.extensions.cqrs.interfaces.commands.ICommand",
        "sagittarius_engine.extensions.cqrs.interfaces.queries.IQuery",
    }
)


def looks_dispatchable(candidate: type) -> bool:
    """
    @brief Whether `candidate` is shaped like something `dispatch()` accepts.

    @details The same test the dispatcher applies implicitly: a callable
    `execute` taking exactly `self` and one DTO. Abstract classes and the
    marker interfaces themselves are excluded — they describe handlers rather
    than being ones, and reporting a finding against `ICommand` would name the
    interface where the reader needs the implementation.
    """
    if inspect.isabstract(candidate):
        return False
    if f"{candidate.__module__}.{candidate.__qualname__}" in _INTERFACE_NAMES:
        return False

    execute = getattr(candidate, "execute", None)
    if not callable(execute):
        return False

    try:
        parameters = inspect.signature(execute).parameters
    except (TypeError, ValueError):
        return False

    return len(parameters) == 2


def discover_handlers(*package_prefixes: str) -> tuple[type, ...]:
    """
    @brief Every dispatchable-looking class defined under the given packages.

    @param package_prefixes Dotted prefixes to search, e.g.
        `"myapp.application"`. Required, and deliberately so: searching
        everything would sweep in third-party classes that happen to have an
        `execute` method and turn the report into noise.

    @details Walks `sys.modules` rather than `pkgutil`, and therefore **imports
    nothing**. Anything the application actually uses is already imported by
    the time it has booted, which is when this runs; importing more to look for
    handlers would execute application code as a side effect of a diagnostic —
    the constraint every check in this package is built around.

    The cost of that choice is honest and worth stating: a handler in a module
    the application has not imported is invisible here. It is also, by the same
    token, a handler nothing can dispatch yet.

    @return Handler classes, sorted by qualified name so two runs of an
        unchanged application produce the same order.
    """
    found: set[type] = set()

    for module_name, module in list(sys.modules.items()):
        if module is None or not module_name.startswith(package_prefixes):
            continue
        for _name, candidate in inspect.getmembers(module, inspect.isclass):
            # `getmembers` returns imported names too; keep only classes this
            # package actually defines, or a handler is reported once per
            # module that imports it.
            if not candidate.__module__.startswith(package_prefixes):
                continue
            if looks_dispatchable(candidate):
                found.add(candidate)

    return tuple(sorted(found, key=lambda c: f"{c.__module__}.{c.__qualname__}"))


def unmatched_prefixes(*package_prefixes: str) -> tuple[str, ...]:
    """
    @brief The given prefixes that match no loaded module at all.

    @details `discover_handlers()` searches `sys.modules`, so a prefix that
    names nothing loaded returns no handlers — indistinguishable, from its
    return value alone, from a package that genuinely contains none. The two
    need different responses: the second is fine, the first means the check the
    operator asked for did not run.

    Separated from `discover_handlers()` rather than folded into it because
    discovery answers "which handlers?" and this answers "was the question even
    answerable?". A caller that only wants handlers should not have to care.

    @return Prefixes with no match, in the order given, so the caller can name
        exactly which argument was wrong.
    """
    loaded = tuple(name for name, module in sys.modules.items() if module is not None)
    return tuple(
        prefix
        for prefix in package_prefixes
        if not any(name.startswith(prefix) for name in loaded)
    )


def as_handler_tuple(handlers: Iterable[type]) -> tuple[type, ...]:
    """@brief Normalises an explicitly supplied handler list, dropping anything
    that is not dispatchable-shaped so a typo in the list is not reported as a
    wiring defect in the application."""
    return tuple(h for h in handlers if isinstance(h, type) and looks_dispatchable(h))
