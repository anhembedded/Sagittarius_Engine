"""Regression tests for TASK-027: the PEP 561 marker must exist in the source
tree AND actually reach the built wheel.

The second half is the part that matters. `pyproject.toml`'s `package-data`
block is the only mechanism shipping non-`.py` files, and it has been wrong
before — it omitted the SDK templates entirely, so a pip-installed engine could
not scaffold (TASK-024). A marker that exists on disk but not in the wheel
gives consumers nothing.
"""

import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "sagittarius_engine"
MARKER_IN_WHEEL = "sagittarius_engine/py.typed"


def test_py_typed_marker_exists_in_source_tree():
    marker = PACKAGE_ROOT / "py.typed"
    assert marker.is_file(), (
        "sagittarius_engine/py.typed is missing. Without it (PEP 561) type "
        "checkers ignore this package's inline annotations entirely and every "
        "consumer sees the engine as untyped."
    )


def test_py_typed_marker_is_declared_in_package_data():
    """Cheap proxy for 'it will ship', with no build required — the expensive
    end-to-end check lives in the wheel test below."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package_data_start = pyproject.index("[tool.setuptools.package-data]")
    package_data_block = pyproject[package_data_start : package_data_start + 600]
    assert '"py.typed"' in package_data_block, (
        "py.typed is not listed in [tool.setuptools.package-data]; it exists on "
        "disk but will not be included in the built wheel."
    )


def test_built_wheel_contains_marker_and_no_stale_qmlshared_assets():
    """End-to-end: whatever wheel is present in dist/ must carry the marker and
    must NOT carry pre-rename QmlShared assets.

    Skipped when dist/ has no wheel, so the normal test run stays fast; the
    release flow (`.agents/rules/release.md`) builds one and this then asserts
    on it.

    The stale-asset half guards a real defect measured 2026-08-23: setuptools
    copies `build/lib/` into the wheel wholesale and never prunes it, so a wheel
    built without `rm -rf build` shipped 9 QML assets that no longer exist in
    the source tree — left over from the 2.0.0 rename that deleted them.
    """
    import pytest

    wheels = (
        sorted((REPO_ROOT / "dist").glob("*.whl"))
        if (REPO_ROOT / "dist").is_dir()
        else []
    )
    if not wheels:
        pytest.skip(
            "no wheel in dist/ — run `rm -rf build dist && python -m build --wheel`"
        )

    names = zipfile.ZipFile(wheels[-1]).namelist()

    assert MARKER_IN_WHEEL in names, (
        f"{wheels[-1].name} does not contain {MARKER_IN_WHEEL} — the marker "
        "exists in the source tree but is not reaching consumers."
    )

    # The .py compatibility shim under QmlShared/ is intentional and stays;
    # only the QML assets were removed by the 2.0.0 rename.
    stale = [n for n in names if "QmlShared" in n and not n.endswith(".py")]
    assert not stale, (
        f"{wheels[-1].name} ships {len(stale)} stale pre-rename QmlShared "
        f"asset(s) absent from the source tree: {stale}. Build with a clean "
        "build/ directory — see .agents/rules/release.md §2."
    )
