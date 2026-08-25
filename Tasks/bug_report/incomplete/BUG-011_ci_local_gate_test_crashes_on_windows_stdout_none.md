# BUG-011 — `test_ci_local_gate_missing_tool` crashes on Windows: `result.stdout` is `None` despite `capture_output=True`

**Reported date:** 2026-08-25
**Severity:** Medium (a `TASK-028` regression guard that cannot report on the one platform it guards)
**Status:** 🔴 Open
**Found by:** `TASK-040`, once the `test` job actually started running again

---

## What is wrong

`tests/test_ci_local_gate_missing_tool.py::test_gate_reports_failure_when_a_required_tool_is_missing`
fails on `windows-latest` — not on its assertions, but before reaching them:

```
tests\test_ci_local_gate_missing_tool.py:71: TypeError
>       output = result.stdout + result.stderr
E       TypeError: unsupported operand type(s) for +: 'NoneType' and 'str'
```

So `result.stdout` is `None` while `result.stderr` is a `str`, from a call that passes
`capture_output=True, text=True`:

```python
result = subprocess.run(
    [_PWSH, "-NoProfile", str(sandbox_gate), "-SkipTests"],
    cwd=tmp_path, env=env,
    capture_output=True, text=True, timeout=GATE_TIMEOUT_SECONDS,
)
```

That combination is supposed to make both attributes strings. Something about how `pwsh` is
launched here — with a deliberately minimal `PATH`, `VIRTUAL_ENV` removed, and `cwd` set to a
`tmp_path` — is leaving the stdout pipe unread.

## Why it matters

This test is the regression guard for `TASK-028`: the local completion gate once printed
*"All local checks passed successfully!"* with exit code 0 while having linted, type-checked and
tested nothing, because PowerShell's `$LASTEXITCODE` is untouched when a tool cannot be resolved
at all.

`ci-local.ps1` is a **PowerShell** script. Windows is the platform this guard most needs to work
on, and it is the only platform where it runs at all — on Linux `shutil.which("pwsh")` returns
`None` and the whole test is skipped. So the guard currently reports on no platform: skipped on
Linux, crashing on Windows. `TASK-028`'s regression is unguarded in practice.

## Reproduction

`windows-latest`, Python 3.12, from the `test` job. Reproduced in two consecutive CI runs on
different commits (`5dbdccd`, `5fab915`), so it is not intermittent.

**Not reproducible in this Linux container**: no `pwsh`, so the test skips. Anyone fixing this
needs a Windows machine or a CI round-trip — which is why no speculative fix was pushed with
`TASK-040`.

## Pre-existing, not introduced by `TASK-040`

Established by comparing the two Windows runs across that change:

| | before (`5dbdccd`) | after (`5fab915`) |
|---|---|---|
| `test_gallery_emits_no_qml_runtime_warnings` | FAILED | FAILED (`BUG-006`) |
| `test_staleness_check_actually_catches_the_original_bug` | FAILED | **fixed** (`TASK-040`) |
| `test_gate_reports_failure_when_a_required_tool_is_missing` | FAILED | FAILED (**this bug**) |
| `test_roster_screen_emits_no_qml_runtime_warnings` | FAILED | passed (`BUG-006` coin-flip) |
| | `4 failed, 1257 passed` | `2 failed, 1259 passed` |

It was invisible before only because the whole job was skipped behind red lint.

## Requirements

1. **Diagnose why `stdout` is `None` before changing the test.** The obvious patch —
   `output = (result.stdout or "") + (result.stderr or "")` — makes the `TypeError` go away
   while leaving the test asserting `"RESULT: FAIL" in output` against output it may not have
   captured. That converts a loud crash into a guard that can pass without having read what the
   gate printed, which is the same class of false-positive `TASK-028` is *about*. Do not apply it
   as the fix.
2. Candidates worth checking, in order: whether `pwsh` re-execs or detaches (leaving the parent's
   pipe unread), whether the minimal `PATH` breaks `pwsh`'s own startup such that it writes only
   to stderr, and whether `-NoProfile` plus a missing `SystemRoot`-derived dependency changes how
   the host attaches its streams.
3. Once the cause is known, assert on the stream that actually carries the gate's output, and keep
   `returncode != 0` as the primary assertion — it is the one that cannot be faked by a capture
   problem.
4. Make the test **fail rather than skip** when `pwsh` is absent *in CI* (an env marker), so a
   guard for a Windows script cannot silently report nothing again. Skipping locally on Linux is
   fine; skipping on the platform under test is not.

## Related

- `TASK-028` — the false-positive gate this test guards against
- `TASK-030` — replaced `pre_commit.ps1` with `scripts/ci-local.ps1`
- `TASK-040` — made the job run, exposing this
- `BUG-006` — the other Windows failure in the same run; unrelated cause
