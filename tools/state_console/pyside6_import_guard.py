"""
@brief Static guard: no `.py` file under `tools/state_console/` imports
`PySide6` at module scope — `EPIC-007E` §2 rule 2, `EPIC-005` §2's D7.

@details In the shape of `sagittarius_engine.extensions.pyside_mvc.import_boundary
.find_deep_imports()` (a regex scan over source text, not an import), for the
same reason that module is a regex scan rather than an import: scanning must
work in an environment that does not have `PySide6` installed at all — the
whole point of `dashboard = ["PySide6>=6.5"]` being an extra.

A module-scope `from PySide6...`/`import PySide6...` is what killed
`sagittarius-audit` (`TASK-002`, `TASK-039`): the command died on
`ModuleNotFoundError` before reaching any of its own code, in a wheel that
declares `PySide6` only as an optional extra. The fix that shipped
(`extensions/audit/cli.py`) imports `websockets` inside the function that
needs it; every module here that touches PySide6 does the same.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

#: Anchored at column 0, deliberately: an import indented under a function
#: or `if TYPE_CHECKING:` block is exactly the sanctioned lazy-import shape
#: this guard exists to allow, not to catch.
_MODULE_SCOPE_PYSIDE6_IMPORT_RE = re.compile(r"^(?:from|import)\s+PySide6\b")


@dataclass(frozen=True)
class PySide6ImportFinding:
    """One module-scope `PySide6` import."""

    file: Path
    line_number: int
    line_text: str


def find_module_scope_pyside6_imports(
    root: Path, exempt_dirs: Iterable[Path] = ()
) -> list[PySide6ImportFinding]:
    """
    @brief Scans every `.py` file under `root` for a `PySide6` import at
    column 0 (module scope).

    @param root Directory to scan recursively.
    @param exempt_dirs Directories excluded entirely.
    @return Findings sorted by file path then line number.
    """
    exempt_dirs = [Path(d).resolve() for d in exempt_dirs]
    findings: list[PySide6ImportFinding] = []

    for py_file in sorted(root.rglob("*.py")):
        resolved = py_file.resolve()
        if any(_is_within(resolved, exempt) for exempt in exempt_dirs):
            continue

        for line_number, line_text in enumerate(
            py_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if _MODULE_SCOPE_PYSIDE6_IMPORT_RE.match(line_text):
                findings.append(
                    PySide6ImportFinding(
                        file=py_file,
                        line_number=line_number,
                        line_text=line_text.strip(),
                    )
                )

    return findings


def _is_within(path: Path, directory: Path) -> bool:
    return directory in path.parents or path == directory


def format_findings(findings: list[PySide6ImportFinding]) -> str:
    """Renders findings as a human-readable block for an assertion failure
    message — file:line and the offending line text."""
    lines = [f"{len(findings)} module-scope PySide6 import(s) found:"]
    for finding in findings:
        lines.append(f"  {finding.file}:{finding.line_number}: {finding.line_text}")
    return "\n".join(lines)
