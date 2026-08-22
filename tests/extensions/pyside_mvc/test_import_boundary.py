"""Tests for the deep-import guard (EPIC-001C follow-up) — the enforcement
mechanism behind ui-architecture.md §8's "only the top-level package is a
supported import surface" consumption contract."""

from __future__ import annotations

from pathlib import Path

from sagittarius_engine.extensions.pyside_mvc.import_boundary import (
    find_deep_imports,
    format_findings,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_finds_a_deep_import_from_a_submodule(tmp_path: Path):
    _write(
        tmp_path / "app.py",
        "from sagittarius_engine.extensions.pyside_mvc.tokens import get_theme_bridge\n",
    )

    findings = find_deep_imports(tmp_path)

    assert len(findings) == 1
    assert findings[0].submodule == "tokens"


def test_finds_a_deep_import_reaching_a_nested_submodule(tmp_path: Path):
    _write(
        tmp_path / "app.py",
        "from sagittarius_engine.extensions.pyside_mvc.runtime.qml_host_view import (\n"
        "    configure_app_qml,\n"
        ")\n",
    )

    findings = find_deep_imports(tmp_path)

    assert len(findings) == 1
    assert findings[0].submodule == "runtime.qml_host_view"


def test_does_not_flag_the_top_level_import(tmp_path: Path):
    _write(
        tmp_path / "app.py",
        "from sagittarius_engine.extensions.pyside_mvc import configure_app_qml\n",
    )

    assert find_deep_imports(tmp_path) == []


def test_does_not_flag_a_bare_module_import_of_the_top_level_package(tmp_path: Path):
    _write(tmp_path / "app.py", "import sagittarius_engine.extensions.pyside_mvc\n")

    assert find_deep_imports(tmp_path) == []


def test_does_not_flag_the_sanctioned_legacy_shims(tmp_path: Path):
    _write(
        tmp_path / "app.py",
        "from sagittarius_engine.extensions.pyside_mvc.base_view import (\n"
        "    DEV_MODE_CONFIG_KEY,\n"
        ")\n"
        "from sagittarius_engine.extensions.pyside_mvc.QmlShared.log_list_model import (\n"
        "    LogListModel,\n"
        ")\n",
    )

    assert find_deep_imports(tmp_path) == []


def test_ignores_unrelated_imports(tmp_path: Path):
    _write(
        tmp_path / "app.py",
        "import os\nfrom pathlib import Path\nfrom PySide6.QtCore import QObject\n",
    )

    assert find_deep_imports(tmp_path) == []


def test_exempt_dirs_are_skipped_entirely(tmp_path: Path):
    vendored = _write(
        tmp_path / "vendored" / "old_code.py",
        "from sagittarius_engine.extensions.pyside_mvc.tokens import get_theme_bridge\n",
    ).parent
    _write(
        tmp_path / "app" / "screen.py",
        "from sagittarius_engine.extensions.pyside_mvc.kit import find_raw_primitives\n",
    )

    findings = find_deep_imports(tmp_path, exempt_dirs=[vendored])

    assert len(findings) == 1
    assert "app" in str(findings[0].file)


def test_format_findings_includes_file_line_and_submodule(tmp_path: Path):
    py = _write(
        tmp_path / "app.py",
        "from sagittarius_engine.extensions.pyside_mvc.safety import safe_ui_action\n",
    )

    findings = find_deep_imports(tmp_path)
    rendered = format_findings(findings)

    assert str(py) in rendered
    assert "pyside_mvc.safety" in rendered
    assert "1 deep import" in rendered
