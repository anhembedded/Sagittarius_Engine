"""
@brief Static guards for `pyside_mvc.widgets` — the QtWidgets counterparts
to the QML kit's `tokens.qml_literal_guard`/`kit.raw_primitive_guard`
(EPIC-006, see `Sagittarius_Elite_Warrior/Tasks/epics/EPIC-006_drop_qml/
DECISION_2026-08-24_widget_architecture.md` §6).

@details
Two guards, matching the two QML ones each has a direct counterpart for:

- `find_inline_stylesheets` — no hardcoded colour literal outside
  `widgets/style.py` (the one file `apply_role()`/`_build_qss()` live in).
  Counterpart to `tokens.qml_literal_guard.find_literal_colors`.
- `find_bare_qt_base_widgets` — no `class X(QFrame)`/`class X(QDialog)`
  outside `widgets/surface.py`/`widgets/overlay.py` themselves. Counterpart
  to `kit.raw_primitive_guard.find_raw_primitives` ("no raw primitive
  authored outside the kit").

No coverage-guard counterpart yet (`kit.gallery_coverage_guard`'s QtWidgets
equivalent) — that guard checks every kit type appears in a showcase, and
no QtWidgets showcase/preview exists yet to check against. Add one once
`Sagittarius_Elite_Warrior`'s `EPIC-006C` (or a dedicated preview harness)
gives this package a real showcase to enforce coverage against.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

#: Same three lengths QML's colour guard matches (`#rgb`/`#rrggbb`/
#: `#aarrggbb`) — Qt's QSS colour literal syntax accepts the same forms.
_HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")

#: Same exemption convention as `qml_literal_guard._EXEMPT_MARKER` — a
#: deliberate, reviewed exception, visible on the same line as the literal.
_EXEMPT_MARKER = "token-exempt"

#: The one file inline-stylesheet literals are permitted in.
_STYLE_MODULE_NAME = "style.py"

#: `class Name(QFrame)` / `class Name(QDialog)` as a direct base — matches
#: only when the class body opens right after (a trailing `metaclass=...`
#: kwarg or multi-base declaration is out of scope for this codebase's
#: current style, same "match the real shape, not every hypothetical" call
#: `raw_primitive_guard` makes for its own two controls).
_BARE_QT_BASE_RE = re.compile(r"^\s*class\s+\w+\((QFrame|QDialog)\)\s*:")

#: Files where `Surface`/`Overlay` themselves legitimately extend
#: `QFrame`/`QDialog` directly — the one sanctioned place per base.
_BASE_DEFINITION_FILES = frozenset({"surface.py", "overlay.py"})


@dataclass(frozen=True)
class InlineStylesheetFinding:
    """One hardcoded colour literal found outside `widgets/style.py`."""

    file: Path
    line_number: int
    line_text: str
    matched: str


@dataclass(frozen=True)
class BareQtBaseFinding:
    """One `QFrame`/`QDialog` subclass declared outside its base's own
    definition file — should extend `Surface`/`Overlay` instead."""

    file: Path
    line_number: int
    line_text: str
    qt_base: str


def find_inline_stylesheets(
    root: Path, exempt_dirs: Iterable[Path] = ()
) -> list[InlineStylesheetFinding]:
    """
    @brief Scans every `.py` file under `root` (except `style.py`) for a
    hardcoded colour literal, returning one finding per occurrence.
    @param exempt_dirs Directories excluded entirely — prefer the inline
    `token-exempt` marker for a single justified literal where possible.
    """
    exempt_dirs = [Path(d).resolve() for d in exempt_dirs]
    findings: list[InlineStylesheetFinding] = []

    for py_file in sorted(root.rglob("*.py")):
        if py_file.name == _STYLE_MODULE_NAME:
            continue
        resolved = py_file.resolve()
        if any(_is_within(resolved, exempt) for exempt in exempt_dirs):
            continue

        for line_number, line_text in enumerate(
            py_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if _EXEMPT_MARKER in line_text:
                continue
            stripped = line_text.strip()
            if stripped.startswith("#"):
                continue
            match = _HEX_COLOR_RE.search(line_text)
            if match is not None:
                findings.append(
                    InlineStylesheetFinding(
                        file=py_file,
                        line_number=line_number,
                        line_text=line_text.strip(),
                        matched=match.group(0),
                    )
                )

    return findings


def find_bare_qt_base_widgets(
    root: Path, exempt_dirs: Iterable[Path] = ()
) -> list[BareQtBaseFinding]:
    """
    @brief Scans every `.py` file under `root` (except `surface.py`/
    `overlay.py`) for a class directly subclassing `QFrame`/`QDialog`,
    returning one finding per occurrence.
    """
    exempt_dirs = [Path(d).resolve() for d in exempt_dirs]
    findings: list[BareQtBaseFinding] = []

    for py_file in sorted(root.rglob("*.py")):
        if py_file.name in _BASE_DEFINITION_FILES:
            continue
        resolved = py_file.resolve()
        if any(_is_within(resolved, exempt) for exempt in exempt_dirs):
            continue

        for line_number, line_text in enumerate(
            py_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = _BARE_QT_BASE_RE.match(line_text)
            if match is not None:
                findings.append(
                    BareQtBaseFinding(
                        file=py_file,
                        line_number=line_number,
                        line_text=line_text.strip(),
                        qt_base=match.group(1),
                    )
                )

    return findings


def _is_within(path: Path, directory: Path) -> bool:
    return directory in path.parents or path == directory


def format_inline_stylesheet_findings(findings: list[InlineStylesheetFinding]) -> str:
    lines = [
        f"{len(findings)} hardcoded colour literal(s) found outside widgets/style.py:"
    ]
    for finding in findings:
        lines.append(
            f"  {finding.file}:{finding.line_number}: {finding.matched}"
            f"    | {finding.line_text}"
        )
    return "\n".join(lines)


def format_bare_qt_base_findings(findings: list[BareQtBaseFinding]) -> str:
    lines = [
        f"{len(findings)} bare Qt base subclass(es) found outside "
        "widgets/surface.py or widgets/overlay.py:"
    ]
    for finding in findings:
        lines.append(
            f"  {finding.file}:{finding.line_number}: extends {finding.qt_base} directly"
            f"    | {finding.line_text}"
        )
    return "\n".join(lines)
