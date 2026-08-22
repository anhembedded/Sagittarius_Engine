"""
@brief Static guard against deep imports into this extension's internal
module structure — the enforcement mechanism behind
`ui-architecture.md` §8's consumption contract: only
`sagittarius_engine.extensions.pyside_mvc`'s top-level re-export surface is
a supported import path. `tokens/`, `kit/`, `runtime/`, `mvc/`, `safety/`
and any nested module are internal layout, free to move.

@details
Without this, a facade (`__init__.py` re-exports, `qmldir` module
indirection) is optional discipline, not a guarantee — exactly the gap
`EPIC-001C`'s directory reorg hit in practice: the reference consumer had
grown 2 real imports reaching past this package's own `__init__.py`
(`...pyside_mvc.base_view`, `...pyside_mvc.QmlShared.log_list_model`),
discovered only by grepping the app repo before moving those files, not by
anything in this repo catching it beforehand.

Intended for scanning a **consuming application's** source (this repo's
own internal code is exempt by nature — code inside the extension
naturally imports its own submodules directly; that is not a boundary
violation, only code *outside* `sagittarius_engine.extensions.pyside_mvc`
reaching in is).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_DEEP_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+sagittarius_engine\.extensions\.pyside_mvc\.([\w.]+)"
)

#: Recorded, reviewed exceptions — real pre-existing external consumers of
#: these exact paths, found in the reference consumer during `EPIC-001C`'s
#: reorg. Not an endorsement of the pattern: both exist *because* a deep
#: import already happened before this guard did, and are the debt it
#: exists to stop from growing. New entries require the same standard —
#: a real, grepped, unavoidable external consumer — not convenience.
SANCTIONED_DEEP_IMPORTS: frozenset[str] = frozenset(
    {
        "base_view",
        "QmlShared.log_list_model",
    }
)


@dataclass(frozen=True)
class DeepImportFinding:
    """One import reaching past the top-level re-export surface."""

    file: Path
    line_number: int
    line_text: str
    submodule: str


def find_deep_imports(
    root: Path, exempt_dirs: Iterable[Path] = ()
) -> list[DeepImportFinding]:
    """
    @brief Scans every `.py` file under `root` for an import of
    `sagittarius_engine.extensions.pyside_mvc.<submodule>` reaching past
    the bare top-level package, excluding `SANCTIONED_DEEP_IMPORTS`.

    @param root Directory to scan recursively — typically a consuming
    app's source tree, not this extension's own (see module docstring).
    @param exempt_dirs Directories excluded entirely.
    @return Findings sorted by file path then line number.
    """
    exempt_dirs = [Path(d).resolve() for d in exempt_dirs]
    findings: list[DeepImportFinding] = []

    for py_file in sorted(root.rglob("*.py")):
        resolved = py_file.resolve()
        if any(_is_within(resolved, exempt) for exempt in exempt_dirs):
            continue

        for line_number, line_text in enumerate(
            py_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = _DEEP_IMPORT_RE.match(line_text)
            if match is None:
                continue
            submodule = match.group(1)
            if submodule in SANCTIONED_DEEP_IMPORTS:
                continue
            findings.append(
                DeepImportFinding(
                    file=py_file,
                    line_number=line_number,
                    line_text=line_text.strip(),
                    submodule=submodule,
                )
            )

    return findings


def _is_within(path: Path, directory: Path) -> bool:
    return directory in path.parents or path == directory


def format_findings(findings: list[DeepImportFinding]) -> str:
    """Renders findings as a human-readable block for an assertion failure
    message — file:line, the submodule reached into, and the offending
    line text."""
    lines = [f"{len(findings)} deep import(s) into pyside_mvc internals found:"]
    for finding in findings:
        lines.append(
            f"  {finding.file}:{finding.line_number}: "
            f"pyside_mvc.{finding.submodule}    | {finding.line_text}"
        )
    return "\n".join(lines)
