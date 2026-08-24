"""`EVENT_CATALOG.md` must match what `EventRegistry` produces right now —
the doc-code-sync backstop for `EPIC-008B`, same role
`tests/test_agents_docs_resolve.py` plays for `.agents/context/`.

Runs `scripts/generate_event_catalog.py` in a fresh subprocess rather than
calling `render_catalog()` in-process: this test file runs inside the same
pytest session as every other test, and several of them (`test_base_event.py`)
define throwaway `BaseEvent` subclasses at module scope that would otherwise
permanently pollute the process-wide `EventRegistry` for the rest of the
session (`EventRegistry` is deliberately process-wide, not test-scoped — see
its module docstring). A subprocess gets a registry populated only by real,
importable event modules, which is the only state this test should judge.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CATALOG_PATH = _REPO_ROOT / "EVENT_CATALOG.md"
_GENERATOR = _REPO_ROOT / "scripts" / "generate_event_catalog.py"


def _generate(output_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(_GENERATOR), str(output_path)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"generate_event_catalog.py failed:\n{result.stdout}\n{result.stderr}"
    )


def test_event_catalog_matches_registry(tmp_path):
    assert _CATALOG_PATH.exists(), (
        "EVENT_CATALOG.md is missing — run "
        "`python scripts/generate_event_catalog.py` and commit the result."
    )

    regenerated = tmp_path / "EVENT_CATALOG.regenerated.md"
    _generate(regenerated)

    committed = _CATALOG_PATH.read_text(encoding="utf-8")
    fresh = regenerated.read_text(encoding="utf-8")

    assert committed == fresh, (
        "EVENT_CATALOG.md is stale — an event was added, removed, or "
        "renamed without regenerating it. Run "
        "`python scripts/generate_event_catalog.py` and commit the diff."
    )


def test_event_catalog_has_no_duplicate_event_names():
    """A duplicate row would mean two registrations collided on the same
    `event_name` — the second silently overwrote the first in the registry
    (a dict keyed by `event_name`), which is exactly the kind of collision
    this catalog exists to surface instead of hide."""
    committed = _CATALOG_PATH.read_text(encoding="utf-8")
    rows = [line for line in committed.splitlines() if line.startswith("| `")]
    event_names = [row.split("|")[1].strip() for row in rows]

    assert len(event_names) == len(set(event_names)), (
        f"Duplicate event_name in EVENT_CATALOG.md: {event_names}"
    )


def test_event_catalog_contains_the_known_baseevent_and_lifecycle_events():
    """A representative sample, not an exhaustive re-listing of the catalog
    (that would be the second source of truth this design exists to avoid)
    — just proof the generator actually reaches both registration paths."""
    committed = _CATALOG_PATH.read_text(encoding="utf-8")

    for expected in (
        "health.updated",
        "app.booted",
        "extension.initializing",
        "runtime.tasks.failed",
        "runtime.hosted.started",
        "runtime.scheduler.started",
    ):
        assert f"`{expected}`" in committed, f"{expected} missing from EVENT_CATALOG.md"
