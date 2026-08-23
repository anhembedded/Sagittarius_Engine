"""Regression tests for TASK-022: the repository must ship the licence text it
declares, and the declaration must not drift from the file.

`pyproject.toml` declaring MIT is a *claim*; the LICENSE file is the *grant*.
MIT itself requires the copyright notice and permission text be included in
distributions, which is impossible if the text does not exist. Automated
licence scanners read the shipped text, not the classifier — so a package with
the metadata and no file can still be flagged unlicensed.
"""

import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LICENSE_PATH = REPO_ROOT / "LICENSE"

# Two clauses MIT requires verbatim; enough to catch a truncated or placeholder
# file without pinning the whole text.
REQUIRED_PHRASES = (
    "Permission is hereby granted, free of charge",
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND',
)


def test_license_file_exists_and_contains_mit_text():
    assert LICENSE_PATH.is_file(), (
        "LICENSE is missing from the repo root while pyproject.toml declares MIT. "
        "The declaration is a claim; the file is the grant."
    )
    text = LICENSE_PATH.read_text(encoding="utf-8")
    assert text.startswith("MIT License"), "LICENSE does not start with 'MIT License'"
    for phrase in REQUIRED_PHRASES:
        assert phrase in text, f"LICENSE is missing required MIT text: {phrase!r}"


def test_license_has_a_real_copyright_line():
    """Guards against a placeholder surviving into a released artifact."""
    text = LICENSE_PATH.read_text(encoding="utf-8")
    copyright_lines = [ln for ln in text.splitlines() if ln.startswith("Copyright (c)")]
    assert len(copyright_lines) == 1, (
        f"expected exactly one 'Copyright (c)' line, found {len(copyright_lines)}"
    )
    line = copyright_lines[0]
    for placeholder in ("<", ">", "[", "]", "YEAR", "NAME", "AUTHOR", "yyyy"):
        assert placeholder not in line, (
            f"LICENSE copyright line still contains placeholder {placeholder!r}: {line!r}"
        )


def test_pyproject_license_declaration_still_says_mit():
    """If someone relicenses, pyproject and LICENSE must move together — this
    fails loudly rather than letting the two silently disagree."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'license = {text = "MIT"}' in pyproject, (
        "pyproject.toml no longer declares MIT, but LICENSE still carries MIT text. "
        "Update both together."
    )


def test_built_distribution_includes_the_license():
    """End-to-end: setuptools is expected to pick up a root LICENSE
    automatically, but TASK-022 req. 3 says verify rather than assume — this
    repo has already shipped wheels missing files it believed were included.

    Skipped when dist/ is empty so the normal run stays fast; the release flow
    (`.agents/rules/release.md`) builds first and this then asserts on it.
    """
    import pytest

    dist = REPO_ROOT / "dist"
    wheels = sorted(dist.glob("*.whl")) if dist.is_dir() else []
    if not wheels:
        pytest.skip("no wheel in dist/ — run `rm -rf build dist && python -m build`")

    names = zipfile.ZipFile(wheels[-1]).namelist()
    licensed = [n for n in names if n.upper().endswith("LICENSE")]
    assert licensed, (
        f"{wheels[-1].name} ships no LICENSE. MIT requires the notice be included "
        "in distributions, and licence scanners read the shipped text."
    )
