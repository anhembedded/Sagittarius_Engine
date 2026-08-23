"""Regression test for TASK-028: the local completion gate must fail loudly,
not silently report success, when a required tool isn't resolvable on PATH.

Historically (pre-`TASK-030`), the old `pre_commit.ps1` gated every step on
`$LASTEXITCODE`, which is only ever set by a native executable actually
running. When PowerShell couldn't resolve `ruff`/`mypy`/`pytest` at all — a
non-terminating shell-level error, no process ever starts — `$LASTEXITCODE`
kept whatever value it already held. The gate sailed through every step and
printed "All local checks passed successfully!" with exit code 0, having
linted, type-checked, and tested nothing. `scripts/ci-local.ps1` fixes this
with `$ErrorActionPreference = "Stop"` plus a `try/catch` around every step;
this test locks that in by reproducing the exact original scenario.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE_SCRIPT = REPO_ROOT / "scripts" / "ci-local.ps1"
GATE_TIMEOUT_SECONDS = 60

_PWSH = shutil.which("pwsh")


@pytest.mark.skipif(_PWSH is None, reason="pwsh not available on PATH")
def test_gate_reports_failure_when_a_required_tool_is_missing():
    # A minimal PATH containing only what's needed to launch pwsh and basic
    # OS utilities -- deliberately excludes anything that could resolve
    # ruff/mypy/pytest, reproducing the missing-tool scenario directly.
    system_root = os.environ.get("SystemRoot", "")
    candidate_dirs = [
        os.path.dirname(_PWSH),
        os.path.join(system_root, "System32") if system_root else "",
        system_root,
        "/usr/bin",
        "/bin",
    ]
    minimal_path = os.pathsep.join(d for d in candidate_dirs if d and os.path.isdir(d))

    env = dict(os.environ)
    env["PATH"] = minimal_path

    result = subprocess.run(
        [_PWSH, "-NoProfile", str(GATE_SCRIPT), "-SkipTests"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_SECONDS,
    )

    output = result.stdout + result.stderr

    assert result.returncode != 0, (
        "Gate exited 0 with required tools missing from PATH -- the exact "
        f"false-positive TASK-028 describes.\n--- output ---\n{output}"
    )
    assert "RESULT: FAIL" in output, f"Expected RESULT: FAIL in output.\n{output}"
    assert "RESULT: PASS" not in output, f"Gate falsely reported PASS.\n{output}"
