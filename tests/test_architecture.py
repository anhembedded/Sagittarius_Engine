import ast
import glob
import os

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
