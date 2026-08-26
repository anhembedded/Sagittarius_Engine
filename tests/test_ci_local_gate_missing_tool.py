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
def test_gate_reports_failure_when_a_required_tool_is_missing(tmp_path):
    # Stripping PATH alone is NOT enough to hide the tools, and asserting on it
    # made this test vacuous: the gate resolves ruff/mypy/pytest from
    # `<repoRoot>/.venv/bin` directly (ci-local.ps1's $venvBinDir), and only falls
    # back to bare names -- the PATH-resolved ones -- when no .venv is found. With
    # the real repo as $repoRoot the venv always wins, so the gate ran the real
    # tools and correctly passed, while this test insisted it should have failed.
    #
    # $repoRoot is `Split-Path -Parent $scriptDir`, so running a copy of the script
    # from `<tmp>/scripts/` makes $repoRoot a directory with no .venv. That forces
    # the bare-name fallback, which the minimal PATH below then cannot resolve --
    # genuinely reproducing the scenario TASK-028 is about.
    sandbox_scripts = tmp_path / "scripts"
    sandbox_scripts.mkdir()
    sandbox_gate = sandbox_scripts / GATE_SCRIPT.name
    shutil.copy2(GATE_SCRIPT, sandbox_gate)

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
    # A venv on VIRTUAL_ENV would be another way for the tools to stay reachable.
    env.pop("VIRTUAL_ENV", None)

    result = subprocess.run(
        # `-File` explicitly. Without it pwsh decides between -File and
        # -Command by inspecting the first argument, and the two modes differ
        # in how they propagate exit codes and where a startup error goes.
        # This is the form ONBOARDING.md documents for running the gate, so
        # the test now exercises the same invocation the humans do.
        [_PWSH, "-NoProfile", "-File", str(sandbox_gate), "-SkipTests"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_SECONDS,
    )

    # `or ""` on both halves: with `capture_output=True` these are normally
    # strings, but on the Windows runner one of them comes back `None`, and
    # `None + str` raised a TypeError on this line -- killing the test while
    # it was assembling a failure *message*, before any of the three
    # assertions below could report what the gate actually did. That made a
    # Windows-only crash look like a gate regression. This is a fix to the
    # diagnostic path only; nothing below is weakened.
    #
    # It stayed hidden because the test skips wherever `pwsh` is absent (so
    # never locally on Linux) and this CI job has been *skipped*, not run,
    # for as long as `lint` was red -- the same gating trap the fix in this
    # commit closes.
    output = (result.stdout or "") + (result.stderr or "")
    detail = (
        f"returncode={result.returncode}, "
        f"stdout={result.stdout!r:.200}, stderr={result.stderr!r:.200}"
    )

    assert result.returncode != 0, (
        "Gate exited 0 with required tools missing from PATH -- the exact "
        f"false-positive TASK-028 describes.\n{detail}\n--- output ---\n{output}"
    )
    assert "RESULT: FAIL" in output, (
        f"Expected RESULT: FAIL in output.\n{detail}\n--- output ---\n{output}"
    )
    assert "RESULT: PASS" not in output, (
        f"Gate falsely reported PASS.\n{detail}\n--- output ---\n{output}"
    )
