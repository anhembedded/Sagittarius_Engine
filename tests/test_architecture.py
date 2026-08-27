import ast
import glob
import os
import pathlib

import pytest

from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.kernel.app import App


def get_imports_in_file(filepath: str) -> list[str]:
    with open(filepath, encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
        except SyntaxError:
            return []

    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.append(node.module)
    return imported_modules


def check_forbidden_imports(directory: str, forbidden_prefixes: list[str]) -> list[str]:
    violations = []
    py_files = glob.glob(os.path.join(directory, "**", "*.py"), recursive=True)
    for filepath in py_files:
        # Ignore tests, temp files
        if "tests" in filepath or "temp" in filepath:
            continue

        imports = get_imports_in_file(filepath)
        for imp in imports:
            for prefix in forbidden_prefixes:
                if imp == prefix or imp.startswith(prefix + "."):
                    violations.append(f"{filepath} imports forbidden module '{imp}'")
    return violations


def test_architectural_dependency_rules():
    base_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "sagittarius_engine")
    )

    # Rule 1: Kernel must NOT import extensions
    kernel_dir = os.path.join(base_dir, "kernel")
    violations = check_forbidden_imports(
        kernel_dir,
        ["sagittarius_engine.extensions"],
    )
    assert not violations, "Kernel dependency violations found:\n" + "\n".join(
        violations
    )

    # Rule 2: Interfaces must NOT import extensions
    interfaces_dir = os.path.join(base_dir, "interfaces")
    violations = check_forbidden_imports(
        interfaces_dir,
        ["sagittarius_engine.extensions"],
    )
    assert not violations, "Interfaces dependency violations found:\n" + "\n".join(
        violations
    )

    # (Rule 4 removed 2026-08-23: it guarded `sagittarius_engine/sdk/`, the
    # project-scaffolding package, which was deleted along with
    # `tools/scaffold.py`. See Tasks/backlog/TASK-024.)


def test_public_api_exports():
    import sagittarius_engine

    public_exports = set(sagittarius_engine.__all__)
    expected_exports = {
        "App",
        "EngineContext",
        "IExtension",
        "ExtensionDescriptor",
    }
    assert public_exports == expected_exports, (
        f"Expected root exports {expected_exports}, got {public_exports}"
    )


def test_bare_import_does_not_pull_in_any_extension():
    """@brief Regression test for TASK-031: importing bare `sagittarius_engine`
    must not transitively import the `extensions` package at all.

    It did — persistence specifically — until `BaseRepository`, `ICommand`,
    and `IQuery` were all dropped from the top-level re-export list. Removing
    only `BaseRepository` was insufficient (this test caught that): Python
    always executes a parent package's `__init__.py` before any of its
    submodules, and `extensions/__init__.py` *was* a barrel that eagerly
    imported every extension's public symbols (persistence's `ISession`
    included, via `health.health_check_query`) — so importing
    `extensions.cqrs` alone for `ICommand`/`IQuery` was enough to trigger the
    whole barrel regardless of which name was asked for. Asserting on the
    barrel itself, not just persistence, is the stronger and more honest
    claim.

    `TASK-034` later made the barrel itself lazy (PEP 562 `__getattr__`) —
    see `test_extensions_barrel_imports_only_the_requested_submodule` below
    for that guard, one level down from this one.

    Run in a subprocess so this reflects only a fresh import, not whatever
    earlier tests in the same process happened to import."""
    import subprocess
    import sys

    script = (
        "import sys\n"
        "import sagittarius_engine\n"
        "assert 'sagittarius_engine.extensions' not in sys.modules, "
        "'bare import pulled in the extensions barrel'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_extensions_barrel_imports_only_the_requested_submodule():
    """@brief Regression test for TASK-034: importing one extension's deep
    submodule path must not import any of its five siblings.

    Same shape as `test_bare_import_does_not_pull_in_any_extension` above,
    one level down — that test guards the root package against the barrel;
    this one guards the barrel itself, now that it's lazy (PEP 562
    `__getattr__` in `extensions/__init__.py`). Before TASK-034, `import
    sagittarius_engine.extensions.cqrs` ran `extensions/__init__.py`'s
    eager imports first (Python always executes a parent package's
    `__init__.py` before a submodule), which pulled in all six extensions
    regardless of which one was actually requested.

    Run in a subprocess so this reflects only a fresh import, not whatever
    earlier tests in the same process happened to import."""
    import subprocess
    import sys

    script = (
        "import sys\n"
        "import sagittarius_engine.extensions.cqrs\n"
        "siblings = ('audit', 'health', 'logger', 'persistence', 'thread_manager')\n"
        "leaked = [s for s in siblings if f'sagittarius_engine.extensions.{s}' in sys.modules]\n"
        "assert not leaked, f'importing .cqrs alone pulled in: {leaked}'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_extensions_getattr_lazy_resolves_only_the_owning_submodule():
    """@brief Accessing one lazily-resolved attribute on the barrel itself
    (`sagittarius_engine.extensions.ICommand`, PEP 562 `__getattr__`) must
    import only `.cqrs` — not any of its five siblings. Complements
    `test_extensions_barrel_imports_only_the_requested_submodule` above,
    which covers the deep-import path; this covers the barrel-attribute
    path `__getattr__` exists for (nothing in either repo actually goes
    through this path today — see `extensions/__init__.py`'s own
    docstring — but the mechanism itself still needs to be correct).

    Run in a subprocess so this reflects only a fresh import."""
    import subprocess
    import sys

    script = (
        "import sys\n"
        "import sagittarius_engine.extensions as ext\n"
        "_ = ext.ICommand\n"
        "siblings = ('audit', 'health', 'logger', 'persistence', 'thread_manager')\n"
        "leaked = [s for s in siblings if f'sagittarius_engine.extensions.{s}' in sys.modules]\n"
        "assert not leaked, f'resolving ext.ICommand pulled in: {leaked}'\n"
        "assert 'sagittarius_engine.extensions.cqrs' in sys.modules\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_extensions_lazy_attrs_cover_all_public_names_and_resolve():
    """@brief Every name in `extensions.__all__` must have an entry in
    `extensions._LAZY_ATTRS`, and every entry must actually resolve — a
    typo in either dict would otherwise surface only the first time some
    caller happens to touch that one specific name (an `AttributeError`
    far from the typo, in an unrelated caller's stack trace)."""
    import sagittarius_engine.extensions as ext

    assert set(ext._LAZY_ATTRS) == set(ext.__all__), (
        "extensions.__all__ and extensions._LAZY_ATTRS have drifted apart"
    )
    for name in ext.__all__:
        assert getattr(ext, name) is not None


def test_extensions_getattr_unknown_name_raises_attribute_error():
    """@brief PEP 562's contract: `__getattr__` must raise `AttributeError`
    for a name it doesn't own, not return `None` or some other sentinel —
    `hasattr()`/`getattr(..., default)` and tooling both depend on this."""
    import sagittarius_engine.extensions as ext

    with pytest.raises(AttributeError):
        _ = ext.DefinitelyNotARealExtensionName


def test_deprecation_warnings():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    # Test deprecated App.execute
    with pytest.warns(DeprecationWarning, match="App.execute is deprecated"):

        class DummyCommand:
            def execute(self, dto):
                return "executed"

        container.bind(DummyCommand, DummyCommand)
        app.execute(DummyCommand, {})

    # Test deprecated App.query
    with pytest.warns(DeprecationWarning, match="App.query is deprecated"):

        class DummyQuery:
            def execute(self, dto):
                return "queried"

        container.bind(DummyQuery, DummyQuery)
        app.query(DummyQuery, {})


# ---------------------------------------------------------------------------
# EPIC-006A: introspection defaults must never apply to a class we ship
# ---------------------------------------------------------------------------
#
# `IEventBus.subscriptions()` and `IContainer.registrations()` are concrete with
# an empty default, so that an implementation outside this repository keeps
# working (`code-rule.md` §L forbids the NotImplementedError alternative). The
# price is that "no subscriptions" and "cannot introspect" look identical from
# the outside.
#
# These two tests buy the guarantee back for anything shipped here: every
# concrete implementation in the package must override, so a caller can trust an
# empty answer from an engine class to mean genuinely empty. A new bus that
# forgets fails here rather than silently reporting nothing to a diagnostic that
# believed it.


def _concrete_implementations(interface):
    """Every non-abstract subclass of `interface` reachable from the package."""
    import importlib
    import inspect
    import pkgutil

    import sagittarius_engine

    for info in pkgutil.walk_packages(
        sagittarius_engine.__path__, "sagittarius_engine."
    ):
        try:
            module = importlib.import_module(info.name)
        except Exception:
            # Import failures are `test_all_modules_importable.py`'s job to
            # report; swallowing them here keeps this test's failure message
            # about the thing it actually checks.
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, interface)
                and obj is not interface
                and not inspect.isabstract(obj)
                and obj.__module__.startswith("sagittarius_engine.")
            ):
                yield obj


def test_event_buses_implement_subscriptions():
    from sagittarius_engine.interfaces import IEventBus

    missing = sorted(
        f"{cls.__module__}.{cls.__qualname__}"
        for cls in set(_concrete_implementations(IEventBus))
        if cls.subscriptions is IEventBus.subscriptions
    )

    assert not missing, (
        "These IEventBus implementations inherit the empty default of "
        "`subscriptions()`, so they report no subscriptions no matter what is "
        "registered on them, and any diagnostic reading them is silently "
        "wrong:\n  " + "\n  ".join(missing)
    )


def test_containers_implement_registrations():
    from sagittarius_engine.interfaces import IContainer

    missing = sorted(
        f"{cls.__module__}.{cls.__qualname__}"
        for cls in set(_concrete_implementations(IContainer))
        if cls.registrations is IContainer.registrations
    )

    assert not missing, (
        "These IContainer implementations inherit the empty default of "
        "`registrations()`, so they report nothing registered no matter what "
        "is bound, and any diagnostic reading them is silently wrong:\n  "
        + "\n  ".join(missing)
    )


def test_async_event_bus_also_implements_subscriptions():
    """`AsyncioEventBus` is not an `IEventBus`.

    It satisfies `IAsyncEventBus`, a Protocol, so it sits in a separate
    hierarchy that `test_event_buses_implement_subscriptions` cannot reach via
    `issubclass`. It is still a bus an application runs on, and `EPIC-006` must
    be able to introspect it, so it is pinned explicitly rather than left to a
    guard that structurally cannot see it.
    """
    from sagittarius_engine.infrastructure.event_bus.asyncio_event_bus import (
        AsyncioEventBus,
    )
    from sagittarius_engine.interfaces import IEventBus

    assert not issubclass(AsyncioEventBus, IEventBus), (
        "if this becomes an IEventBus, delete this test — the generic guard "
        "above covers it and this one would be redundant"
    )
    assert callable(getattr(AsyncioEventBus, "subscriptions", None))
    assert AsyncioEventBus.subscriptions is not IEventBus.subscriptions


# ── Function-local imports: bounded, not forbidden (REF-001) ────────────────
#
# `code-rule.md` §45 read "Never place `import ...` inside functions", and the
# engine did it 32 times. A rule nothing enforces is not a rule; §45 now names
# two bounded exceptions and this guard is what bounds them.
#
# Same shape as `import_boundary.SANCTIONED_DEEP_IMPORTS`, which
# `design-discipline.md` cites as the reference case for debt that is *named,
# justified and unable to grow*.

#: `(path, imported module)` pairs permitted to import inside a function.
#: Adding a row is a deliberate act that shows up in review, which is the whole
#: point — see `REF-001` for the two categories and what each one costs.
SANCTIONED_LOCAL_IMPORTS: frozenset[tuple[str, str]] = frozenset(
    {
        # -- Category A: an optional dependency, at its single point of failure.
        # The wheel declares no dependencies. Hoisting any of these makes the
        # module unimportable without a package the engine does not require,
        # which is `EPIC-005` §2's D7 exactly.
        ("sagittarius_engine/extensions/audit/cli.py", "websockets.exceptions"),
        ("sagittarius_engine/extensions/audit/cli.py", "websockets.sync.client"),
        (
            "sagittarius_engine/extensions/audit/infra/trace_server.py",
            "websockets.asyncio.server",
        ),
        (
            "sagittarius_engine/extensions/audit/exporters/otel.py",
            "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        ),
        (
            "sagittarius_engine/extensions/audit/exporters/otel.py",
            "opentelemetry.sdk.resources",
        ),
        (
            "sagittarius_engine/extensions/audit/exporters/otel.py",
            "opentelemetry.sdk.trace",
        ),
        (
            "sagittarius_engine/extensions/audit/exporters/otel.py",
            "opentelemetry.sdk.trace.export",
        ),
        ("sagittarius_engine/extensions/health/health_check_query.py", "sqlalchemy"),
        (
            "sagittarius_engine/infrastructure/config/config_sources/dotenv_source.py",
            "dotenv",
        ),
        # -- Category B: an intra-engine import whose comment claims a cycle.
        # REF-001 measured that all eleven currently hoist in isolation, so the
        # claim may be stale — but "imports fine when imported first" does not
        # disprove an order-dependent cycle, and hoisting on that evidence would
        # be exactly the "it works now" diagnosis `design-discipline.md`
        # refuses. Sanctioned pending the stricter multi-order check REF-001
        # leaves open; every one is a candidate for removal, not a precedent.
        (
            "sagittarius_engine/extensions/diagnostics/runtime.py",
            "sagittarius_engine.domain.event_registry",
        ),
        (
            "sagittarius_engine/infrastructure/config/config_manager.py",
            "sagittarius_engine.infrastructure.config.dict_source",
        ),
        (
            "sagittarius_engine/infrastructure/config/config_manager.py",
            "sagittarius_engine.infrastructure.config.env_source",
        ),
        (
            "sagittarius_engine/infrastructure/config/config_manager.py",
            "sagittarius_engine.infrastructure.config.json_source",
        ),
        (
            "sagittarius_engine/kernel/context.py",
            "sagittarius_engine.interfaces.i_dispatcher",
        ),
        (
            "sagittarius_engine/kernel/context.py",
            "sagittarius_engine.runtime.async_runtime.async_runtime",
        ),
        (
            "sagittarius_engine/kernel/context.py",
            "sagittarius_engine.runtime.hosted.hosted_service_manager",
        ),
        (
            "sagittarius_engine/kernel/context.py",
            "sagittarius_engine.runtime.scheduler.scheduler",
        ),
        (
            "sagittarius_engine/kernel/context.py",
            "sagittarius_engine.runtime.tasks.task_manager",
        ),
        (
            "sagittarius_engine/kernel/context.py",
            "sagittarius_engine.utils.null_logger",
        ),
        (
            "sagittarius_engine/kernel/module_auto_discovery.py",
            "sagittarius_engine.kernel.module_loader",
        ),
    }
)


def find_function_local_imports(
    root: str = "sagittarius_engine",
) -> set[tuple[str, str]]:
    """
    @brief Every `(path, module)` imported inside a function body.

    @details Walks the AST rather than grepping, so an import nested in a
    `try`, an `except`, or a closure is found the same as a top-level one in
    the function — those are precisely where they hide.
    """
    found: set[tuple[str, str]] = set()
    for path in sorted(pathlib.Path(root).rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Import):
                    for alias in inner.names:
                        found.add((path.as_posix(), alias.name))
                elif isinstance(inner, ast.ImportFrom):
                    found.add((path.as_posix(), inner.module or ""))
    return found


def test_state_console_imports_nothing_outside_stdlib_and_this_engine():
    """`EPIC-007C` criterion 7: `extensions/state_console/` imports only the
    stdlib and this engine's own modules — never PySide6, never anything
    from `tools/`."""
    import sys

    root = pathlib.Path(__file__).resolve().parent.parent / (
        "sagittarius_engine/extensions/state_console"
    )
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                # node.level > 0 is a relative import (`from .extension import
                # ...`) — a same-package sibling, not a third-party module.
                modules = [node.module]
            else:
                continue
            for module in modules:
                top = module.split(".")[0]
                if top in ("__future__", "sagittarius_engine"):
                    continue
                if top not in sys.stdlib_module_names:
                    violations.append(f"{path}: imports {module!r}")

    assert not violations, (
        "extensions/state_console/ imported outside the stdlib and this "
        "engine's own package:\n  " + "\n  ".join(violations)
    )


def test_no_unsanctioned_function_local_imports():
    """`code-rule.md` §45's two exceptions, and nothing beyond them.

    A new function-local import fails here rather than passing review as
    "everyone else does it" — which is how thirty-two of them accumulated
    under a rule that said "never".
    """
    unsanctioned = sorted(find_function_local_imports() - SANCTIONED_LOCAL_IMPORTS)

    assert not unsanctioned, (
        "function-local import(s) outside code-rule.md §45's two exceptions:\n  "
        + "\n  ".join(f"{path} -> {module}" for path, module in unsanctioned)
        + "\n\nHoist it to module scope. If it is an optional dependency at its "
        "point of failure, or genuinely breaks an import cycle, add it to "
        "SANCTIONED_LOCAL_IMPORTS with a comment saying which and why."
    )


def test_every_sanctioned_local_import_still_exists():
    """The allowlist shrinks when a site is fixed; it must not keep stale rows.

    A guard whose allowlist outlives what it excuses stops being a bound and
    becomes a list nobody reads.
    """
    stale = sorted(SANCTIONED_LOCAL_IMPORTS - find_function_local_imports())

    assert not stale, (
        "SANCTIONED_LOCAL_IMPORTS names site(s) that no longer exist — delete "
        "these rows:\n  " + "\n  ".join(f"{path} -> {module}" for path, module in stale)
    )
