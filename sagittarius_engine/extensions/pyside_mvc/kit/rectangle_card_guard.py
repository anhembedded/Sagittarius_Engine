"""
@brief Static guard against a bare `Rectangle` reimplementing `BaseCard`'s
own visual recipe — the "Rectangle-as-styled-card" gap `raw_primitive_guard`
deliberately left open (see its module docstring). The third guard in the
same family: `qml_literal_guard` checks *values* (no literal colours),
`raw_primitive_guard` checks *authorship* of two specific controls
(`Button`/`CheckBox`), this one checks *shape* — a `Rectangle` block that
carries the same background+border+radius combination every real
`BaseCard`-derived component uses (see `TimeRangeCard.qml`: `color:
Theme.bgCard`, `border.color: Theme.border`, `border.width: 1`, `radius:
8`) instead of actually deriving `BaseCard`.

@details
Why this needs block-scoped parsing, not a per-line regex like its two
siblings: the violation is a *combination* of three separate property
lines that must all belong to the same `Rectangle`'s own direct properties
— not to a nested child's. A per-line match would misattribute a nested
`Rectangle { border.color: ... }` inside an outer `Rectangle { color: ... }`
as one violation spanning both. This module tracks brace depth instead, so
only properties declared directly inside a given `Rectangle {`'s own braces
(depth 1 relative to it) count toward it.

Deliberately conservative, matching the "precision over completeness"
choice both sibling guards already made:
- Requires **all three** of `color`, `radius`, and (`border.color` or
  `border.width`) as direct properties before flagging — this is the exact
  recipe real card components use (background + border + radius), not a
  partial match. A plain divider (`color` + a thin `height`/`width`, no
  border/radius) or a spacer (`Layout.fillWidth`, no `color` at all) never
  matches; a colour-only badge/dot never matches either. Some legitimate
  Rectangle uses that happen to combine all three (a non-card panel with a
  documented reason) can still exist — see the exemption marker below,
  mirroring `qml_literal_guard`'s `token-exempt` convention rather than
  `raw_primitive_guard`'s no-exemption stance, since (unlike a bare
  `Button`/`CheckBox`) a justified case genuinely exists here.
- Only the **dotted** `border.color:`/`border.width:` property syntax is
  recognised — the grouped `border { color: ...; width: ... }` attached-
  property-group form is not, since it does not appear anywhere in this
  codebase today (verified by search); add it if that ever changes rather
  than guessing at the syntax now.
- Only `Rectangle` itself is covered, not `Item`/`Pane`/other roots — the
  gap this module closes was named specifically as "Rectangle-as-styled-
  card" (`EPIC-001C` implementation notes).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

#: A `Rectangle` declared as the root of a QML block — anchored at the start
#: of a line (after indentation only), same convention as
#: `raw_primitive_guard`'s `_RAW_PRIMITIVE_RE`.
_RECTANGLE_ROOT_RE = re.compile(r"^\s*Rectangle\s*\{")

_COLOR_PROP_RE = re.compile(r"^\s*color\s*:")
_BORDER_COLOR_PROP_RE = re.compile(r"^\s*border\.color\s*:")
_BORDER_WIDTH_PROP_RE = re.compile(r"^\s*border\.width\s*:")
_RADIUS_PROP_RE = re.compile(r"^\s*radius\s*:")

#: A `Rectangle {` header line carrying this marker is a deliberate,
#: reviewed exception — same "justified at the call site" contract
#: ui-architecture.md §1.1 requires of the escape hatch itself, just spelled
#: as its own marker since this axis (shape, not a literal value) is
#: distinct from `qml_literal_guard`'s `token-exempt`.
_EXEMPT_MARKER = "card-exempt"


@dataclass(frozen=True)
class RectangleCardFinding:
    """One `Rectangle` block found reimplementing the card visual recipe
    (background + border + radius) instead of deriving `BaseCard`."""

    file: Path
    line_number: int
    line_text: str


def find_rectangle_as_styled_cards(
    root: Path, exempt_dirs: Iterable[Path] = ()
) -> list[RectangleCardFinding]:
    """
    @brief Scans every `.qml` file under `root` for a `Rectangle` block
    root whose own direct properties combine `color`, `radius`, and a
    `border.color`/`border.width` — the same background+border+radius
    recipe every real `BaseCard`-derived component uses — without actually
    deriving `BaseCard`.

    @param root Directory to scan recursively — typically a consuming app's
    screens directory, not the kit itself.
    @param exempt_dirs Directories excluded entirely — pass the kit's own
    location(s) when scanning a tree that contains it: legitimate kit
    primitives (e.g. `FieldBackground.qml`) carry this exact shape on
    purpose and are not "a screen reimplementing a card."
    @return Findings sorted by file path then line number.
    """
    exempt_dirs = [Path(d).resolve() for d in exempt_dirs]
    findings: list[RectangleCardFinding] = []

    for qml_file in sorted(root.rglob("*.qml")):
        resolved = qml_file.resolve()
        if any(_is_within(resolved, exempt) for exempt in exempt_dirs):
            continue
        findings.extend(_scan_file(qml_file))

    return findings


def _scan_file(qml_file: Path) -> list[RectangleCardFinding]:
    lines = qml_file.read_text(encoding="utf-8").splitlines()
    findings: list[RectangleCardFinding] = []

    for index, header in enumerate(lines):
        if not _RECTANGLE_ROOT_RE.match(header) or _EXEMPT_MARKER in header:
            continue
        # Each `Rectangle {` header — including one nested inside another
        # Rectangle's block — is scanned independently for its OWN direct
        # properties, so a nested candidate is never shadowed by its
        # (non-matching) parent's scan already having walked past it.
        _end_index, has_color, has_border, has_radius = _scan_block(lines, index)
        if has_color and has_border and has_radius:
            findings.append(
                RectangleCardFinding(
                    file=qml_file,
                    line_number=index + 1,
                    line_text=header.strip(),
                )
            )

    return findings


def _scan_block(lines: list[str], header_index: int) -> tuple[int, bool, bool, bool]:
    """Walks forward from a `Rectangle {` header line, tracking brace depth,
    and reports whether its own direct (depth-1) properties include
    `color`, a border property, and `radius`. Returns the index of the line
    where this block's own closing brace was found (or the last line, if
    the file ends with the block still open — malformed QML is not this
    guard's concern to diagnose)."""
    header = lines[header_index]
    depth = header.count("{") - header.count("}")
    has_color = False
    has_border = False
    has_radius = False

    line_index = header_index
    while depth > 0 and line_index + 1 < len(lines):
        line_index += 1
        line = lines[line_index]
        stripped = line.strip()
        if depth == 1 and not stripped.startswith(("//", "*")):
            if _COLOR_PROP_RE.match(line):
                has_color = True
            elif _BORDER_COLOR_PROP_RE.match(line) or _BORDER_WIDTH_PROP_RE.match(line):
                has_border = True
            elif _RADIUS_PROP_RE.match(line):
                has_radius = True
        depth += line.count("{") - line.count("}")

    return line_index, has_color, has_border, has_radius


def _is_within(path: Path, directory: Path) -> bool:
    return directory in path.parents or path == directory


def format_findings(findings: list[RectangleCardFinding]) -> str:
    """Renders findings as a human-readable block for an assertion failure
    message — file:line and the offending `Rectangle {` declaration."""
    lines = [
        (
            f"{len(findings)} Rectangle block(s) reimplementing the card visual "
            "recipe (color + border + radius) instead of deriving BaseCard:"
        )
    ]
    for finding in findings:
        lines.append(f"  {finding.file}:{finding.line_number}: {finding.line_text}")
    return "\n".join(lines)
