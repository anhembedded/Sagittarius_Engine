"""
@brief Package namespace for Sagittarius extensions — lazily resolved (PEP 562).

@details
`architecture.md` describes these as "opt-in feature packages, each
independently composable." Before this file (`TASK-034`), the barrel
contradicted that: it imported every extension's public symbols eagerly at
package-import time, and Python always runs a package's `__init__.py` in
full before any of its submodules — so `from
sagittarius_engine.extensions.cqrs import ICommand` alone pulled in
`.audit`, `.health` (and transitively `.persistence`'s `ISession`, via
`health_check_query.py`), `.logger`, and `.thread_manager` too. Nothing
crashed (each extension's own optional dependency, e.g. `.persistence`'s
`sqlalchemy`, is separately guarded), but every consumer paid the full
import cost regardless of which single extension it actually wanted.

`__getattr__`/`__dir__` below (PEP 562) resolve each name in `__all__`
against `_LAZY_ATTRS` and import only the one submodule that defines it, on
first access — never its siblings. Verified before this change (`grep`,
both this repo's own source/tests/examples/tools and
`Sagittarius_Elite_Warrior`): nothing imports through this barrel path
(`from sagittarius_engine.extensions import X`) anywhere. Every real caller
already imports the deep submodule directly (e.g. `from
sagittarius_engine.extensions.health.health_module import HealthExtension`),
which this change leaves untouched.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    # CQRS
    "ICommand",
    "IQuery",
    # Audit
    "AuditExtension",
    "AuditService",
    # Persistence
    "BaseRepository",
    "ISession",
    "SQLAlchemySessionAdapter",
    "DatabaseExtension",
    "SqlAlchemyExtension",
    # Health
    "HealthExtension",
    "HealthCheckQuery",
    "HealthCheckDTO",
    "HealthUpdatedEvent",
    # Logger
    "LoggerExtension",
    # Thread Manager
    "ThreadManagerModule",
    # Diagnostics (EPIC-006)
    "DiagnosticsExtension",
    "WiringInspector",
    "WiringReport",
]

#: Maps each public name to the one submodule that defines it. Exhaustive —
#: every entry in `__all__` must appear here, checked by this package's own
#: test (`tests/test_architecture.py::test_extensions_lazy_attrs_cover_all`).
_LAZY_ATTRS: dict[str, str] = {
    "ICommand": ".cqrs",
    "IQuery": ".cqrs",
    "AuditExtension": ".audit",
    "AuditService": ".audit",
    "BaseRepository": ".persistence",
    "ISession": ".persistence",
    "SQLAlchemySessionAdapter": ".persistence",
    "DatabaseExtension": ".persistence",
    "SqlAlchemyExtension": ".persistence",
    "HealthExtension": ".health.health_module",
    "HealthUpdatedEvent": ".health.health_module",
    "HealthCheckQuery": ".health.health_check_query",
    "HealthCheckDTO": ".health.health_check_query",
    "LoggerExtension": ".logger.logger_module",
    "ThreadManagerModule": ".thread_manager.thread_manager_module",
    "DiagnosticsExtension": ".diagnostics",
    "WiringInspector": ".diagnostics",
    "WiringReport": ".diagnostics",
}


def __getattr__(name: str) -> Any:
    """PEP 562 module-level hook — `Any` is the signature the typing spec
    mandates for it (the resolved value's real type is whatever
    `_LAZY_ATTRS[name]`'s submodule defines), not a general exception to
    `code-rule.md`'s "avoid `Any`"."""
    module_path = _LAZY_ATTRS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_path, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
