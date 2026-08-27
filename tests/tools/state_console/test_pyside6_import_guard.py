"""Tests for the module-scope PySide6 import guard — `EPIC-007E` criterion 5,
in the shape of `pyside_mvc.import_boundary`'s own tests."""

from __future__ import annotations

from pathlib import Path

from tools.state_console.pyside6_import_guard import (
    find_module_scope_pyside6_imports,
    format_findings,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_finds_a_module_scope_from_import(tmp_path: Path):
    _write(tmp_path / "main.py", "from PySide6.QtWidgets import QApplication\n")

    findings = find_module_scope_pyside6_imports(tmp_path)

    assert len(findings) == 1
    assert "QApplication" in findings[0].line_text


def test_finds_a_module_scope_bare_import(tmp_path: Path):
    _write(tmp_path / "main.py", "import PySide6\n")

    assert len(find_module_scope_pyside6_imports(tmp_path)) == 1


def test_does_not_flag_an_import_inside_a_function(tmp_path: Path):
    _write(
        tmp_path / "main.py",
        "def main() -> int:\n    from PySide6.QtWidgets import QApplication\n    return 0\n",
    )

    assert find_module_scope_pyside6_imports(tmp_path) == []


def test_ignores_unrelated_imports(tmp_path: Path):
    _write(
        tmp_path / "main.py",
        "import os\nfrom pathlib import Path\nfrom sagittarius_engine.kernel import App\n",
    )

    assert find_module_scope_pyside6_imports(tmp_path) == []


def test_exempt_dirs_are_skipped_entirely(tmp_path: Path):
    vendored = _write(
        tmp_path / "vendored" / "old.py", "from PySide6.QtCore import QObject\n"
    ).parent
    _write(tmp_path / "app" / "screen.py", "from PySide6.QtCore import QObject\n")

    findings = find_module_scope_pyside6_imports(tmp_path, exempt_dirs=[vendored])

    assert len(findings) == 1
    assert "app" in str(findings[0].file)


def test_format_findings_includes_file_and_line(tmp_path: Path):
    py = _write(tmp_path / "main.py", "import PySide6.QtWidgets\n")

    findings = find_module_scope_pyside6_imports(tmp_path)
    rendered = format_findings(findings)

    assert str(py) in rendered
    assert "1 module-scope PySide6 import" in rendered


# ------------------------------------------------------- the real tree, live


def test_tools_state_console_has_no_module_scope_pyside6_import():
    """`EPIC-007E` criterion 5, against the actual package.

    `presentation/` is exempt: a `Property`/`Signal`-decorated `QObject`
    subclass (a View, ViewModel, or Presenter) needs `PySide6.QtCore` at
    class-definition time -- Qt's meta-object machinery has no lazy form of
    that. The property this test actually guards is packaging safety
    (`main.py` -- the entry point `verify_wheel_importable.py` resolves --
    imports nothing under `presentation/` at its own module scope, so
    `ep.load()` succeeds with PySide6 absent), not "no Qt class exists
    anywhere in this package", which would rule out building a Qt GUI at
    all. `main.py` and `infrastructure/` (the websocket client, the theme
    wiring) have no such need and are held to the strict rule."""
    root = Path(__file__).resolve().parents[3] / "tools" / "state_console"

    findings = find_module_scope_pyside6_imports(
        root, exempt_dirs=[root / "presentation"]
    )

    assert findings == [], format_findings(findings)


def test_main_py_itself_has_no_module_scope_pyside6_import():
    """The one file `verify_wheel_importable.py`'s `ep.load()` actually
    imports -- held to the rule with no exemption at all."""
    main_py = (
        Path(__file__).resolve().parents[3] / "tools" / "state_console" / "main.py"
    )

    findings = find_module_scope_pyside6_imports(main_py.parent)
    findings = [f for f in findings if f.file == main_py]

    assert findings == [], format_findings(findings)
