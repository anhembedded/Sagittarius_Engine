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
- `find_bare_qt_base_widgets` — no `class X(QFrame)`/`class X(QDialog)`/
  `class X(QWidget)` outside `widgets/surface.py`/`widgets/overlay.py`
  themselves, barring a `# base-exempt: <reason>` line. Counterpart to
  `kit.raw_primitive_guard.find_raw_primitives` ("no raw primitive authored
  outside the kit").

The coverage-guard counterpart (`kit.gallery_coverage_guard`'s QtWidgets
equivalent) exists as of EPIC-007C, but not as a function here: it needs a
running `QApplication` to construct the gallery, which every other guard in
this module deliberately does not. It lives in
`tests/extensions/pyside_mvc/widgets/test_showcase_coverage.py`, reading
`tools.widget_showcase.showcased_types()`, and fails when a type in
`widgets.__all__` is never built by the showcase.

Both guards here scan text, so neither needs Qt. Within *this* repo they are
still exercised only through `tmp_path` fixtures — pointing them at
`sagittarius_engine/` itself remains outstanding.

The consuming app wired them up in EPIC-007D/E
(`tests/unit/presentation/ui/test_widget_guards_hold.py`): colour literals
locked at zero, bare Qt bases held under a ratchet that may only fall. That
is what `colour_source_names` exists for — an app's palette module is its
`style.py`, and until it could be named, the guard reported that file for
containing the very tokens it defines, which put zero out of reach.
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

#: The one file inline-stylesheet literals are permitted in, for this
#: package's own tree. A consuming app keeps its colours somewhere else —
#: the reference consumer's is `assets/palette.py` — and names it through
#: `find_inline_stylesheets`'s `colour_source_names`. Hardcoding this one
#: name meant an app could never reach zero findings: the file defining its
#: tokens was itself reported, fifteen times, for containing tokens.
_STYLE_MODULE_NAME = "style.py"

#: `class Name(QFrame)` / `class Name(QDialog)` / `class Name(QWidget)` as a
#: direct base — matches only when the class body opens right after (a
#: trailing `metaclass=...` kwarg or multi-base declaration is out of scope
#: for this codebase's current style, same "match the real shape, not every
#: hypothetical" call `raw_primitive_guard` makes for its own two controls).
#:
#: `QWidget` joined the set in EPIC-007A. Measured on the consuming app the
#: day it was added: `QFrame`/`QDialog` alone found 12 classes in
#: `Sagittarius_Elite_Warrior/src/presentation/ui`, while 9 more were
#: surfaces authored as `class X(QWidget)` and sailed straight through —
#: `LogPanelWidget`, `AppProgressBarWidget`, `TimeRangeCardWidget`,
#: `DevBoardPanel`, `BackTestTopPanel`, `BackTestTradeLogsPanel`,
#: `DynamicTabBarWidget`, `_CachedFrameOverlay`, `_BotParamFieldWidget`. The
#: "12" this guard used to report was a floor, not a count.
_BARE_QT_BASE_RE = re.compile(r"^\s*class\s+\w+\((QFrame|QDialog|QWidget)\)\s*:")

#: Files where `Surface`/`Overlay` themselves legitimately extend
#: `QFrame`/`QDialog` directly — the one sanctioned place per base.
#:
#: `QWidget` has no entry here on purpose: this package derives no surface
#: from it (`Surface` is a `QFrame`, `Overlay` a `QDialog`), so there is no
#: sanctioned file to name. A legitimate `QWidget` base outside this package
#: — a pure layout composite, an MVC view root — is waved through by
#: `_BASE_EXEMPT_RE` below, per case and with its reason in the source,
#: rather than by exempting a whole file.
_BASE_DEFINITION_FILES = frozenset({"surface.py", "overlay.py"})

#: A class declaration line carrying `# base-exempt: <reason>` is a
#: deliberate, reviewed exception.
#:
#: Its own marker, not `find_inline_stylesheets`'s `token-exempt` — exactly
#: the call `kit.rectangle_card_guard` already made when it spelled its
#: escape hatch `card-exempt`: the axis here is a **base class**, not a
#: literal value, and one marker per axis keeps an exemption from silencing
#: a guard it was never reviewed against. EPIC-007A's task file asked for
#: `token-exempt` to be reused; that predates noticing `card-exempt`'s
#: precedent, and the deviation is recorded in the task file.
#:
#: Stricter than both older markers in one way: the reason is **required**,
#: not merely conventional. `token-exempt`/`card-exempt` match on presence
#: alone, so a bare marker silences them. This axis is new, so nothing
#: depends on the looser spelling, and an exemption nobody justified is how
#: a guard quietly stops meaning anything.
_BASE_EXEMPT_RE = re.compile(r"#\s*base-exempt\s*:\s*\S")


@dataclass(frozen=True)
class InlineStylesheetFinding:
    """One hardcoded colour literal found outside `widgets/style.py`."""

    file: Path
    line_number: int
    line_text: str
    matched: str


@dataclass(frozen=True)
class BareQtBaseFinding:
    """One `QFrame`/`QDialog`/`QWidget` subclass declared outside its base's
    own definition file — should extend `Surface`/`Overlay` instead, or say
    why not with `# base-exempt: <reason>`."""

    file: Path
    line_number: int
    line_text: str
    qt_base: str


def find_inline_stylesheets(
    root: Path,
    exempt_dirs: Iterable[Path] = (),
    colour_source_names: Iterable[str] = (),
) -> list[InlineStylesheetFinding]:
    """
    @brief Scans every `.py` file under `root` for a hardcoded colour
    literal, returning one finding per occurrence.
    @param exempt_dirs Directories excluded entirely — prefer the inline
    `token-exempt` marker for a single justified literal where possible.
    @param colour_source_names File names that legitimately *define* colours
    and so are skipped, alongside this package's own `style.py`. A consuming
    app passes its palette module here (the reference consumer:
    `("palette.py",)`).

    @details Matched by file name, not path, because that is what the
    existing `style.py` skip and `_BASE_DEFINITION_FILES` both already do —
    a second matching convention in the same module would be the more
    surprising choice. Names are exact, so a file merely containing
    "palette" is not excused.
    """
    exempt_dirs = [Path(d).resolve() for d in exempt_dirs]
    skipped_names = {_STYLE_MODULE_NAME, *colour_source_names}
    findings: list[InlineStylesheetFinding] = []

    for py_file in sorted(root.rglob("*.py")):
        if py_file.name in skipped_names:
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
    `overlay.py`) for a class directly subclassing `QFrame`/`QDialog`/
    `QWidget`, returning one finding per occurrence.
    @details A class line carrying `# base-exempt: <reason>` is skipped —
    `QWidget` in particular is a legitimate base for something that is not a
    surface at all (a pure layout composite, an MVC view root), which
    `QFrame`/`QDialog` never were.
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
            if _BASE_EXEMPT_RE.search(line_text):
                continue
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
