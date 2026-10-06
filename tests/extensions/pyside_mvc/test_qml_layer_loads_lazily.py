"""
@brief BUG-023 — importing `pyside_mvc` or its workbench must not load the
QML layer (`kit.card_model`, `runtime.base_view_model`).

@details PySide6 6.9-6.11 leaks one uncollectable object per `QObject`
class that defines a `QtCore.Property` and is alive at interpreter exit, so
a process that merely imports the package prints
`gc: N uncollectable objects at shutdown`. Both checks run in a subprocess:
`sys.modules` and interpreter exit are process-global, and this suite has
long since imported the QML layer in-process.
"""

from __future__ import annotations

import os
import subprocess
import sys

_PKG = "sagittarius_engine.extensions.pyside_mvc"
_ENV = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}


def _run(code: str, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *flags, "-c", code],
        capture_output=True,
        text=True,
        env=_ENV,
        timeout=120,
        check=False,
    )


def test_importing_the_package_and_workbench_does_not_load_the_qml_layer() -> None:
    result = _run(
        "import sys\n"
        f"import {_PKG}\n"
        f"import {_PKG}.workbench\n"
        f"loaded = [m for m in ('{_PKG}.kit.card_model', '{_PKG}.runtime.base_view_model')"
        " if m in sys.modules]\n"
        "assert not loaded, loaded\n"
    )
    assert result.returncode == 0, result.stderr


def test_the_interpreter_exits_without_an_uncollectable_line_after_importing_the_workbench() -> (
    None
):
    result = _run(f"import {_PKG}.workbench", "-W", "always::ResourceWarning")
    assert result.returncode == 0, result.stderr
    assert "uncollectable" not in result.stderr, result.stderr


def test_the_lazy_names_stay_importable_from_every_level() -> None:
    result = _run(
        f"from {_PKG} import BaseQmlViewModel, QmlHostView, OverlayHost\n"
        f"from {_PKG}.runtime import BaseQmlViewModel as B2\n"
        f"from {_PKG}.kit import CardModel\n"
        f"import {_PKG} as p\n"
        "assert BaseQmlViewModel is B2\n"
        "assert all(hasattr(p, n) for n in p.__all__), [n for n in p.__all__ if not hasattr(p, n)]\n"
        "ns = {}\n"
        f"exec('from {_PKG} import *', ns)\n"
        "assert 'QmlHostView' in ns\n"
    )
    assert result.returncode == 0, result.stderr
