# TASK-028: `pre_commit.ps1` reports "all checks passed" when a tool isn't even on `PATH`

> **Status update 2026-08-23 (after `TASK-030`):** `pre_commit.ps1` was replaced wholesale by
> `scripts/ci-local.ps1` in `TASK-030`, which cites this task in its commit message. **Requirement
> 1 is done, verified empirically** — the new script sets `$ErrorActionPreference = "Stop"` and
> wraps every step in `try/catch`, so a command-not-found is now a caught, terminating error
> instead of a silently-ignored non-terminating one. Re-ran the exact false-positive scenario
> against the new script on this machine (`PATH` with no `ruff`/`mypy`/`pytest` resolvable):
> result was `RESULT: FAIL` / `FAILED_STEPS: Ruff Lint,Ruff Format,Mypy`, not a false pass. The
> gate no longer lies about having run.
>
> **Requirement 2 (a regression test for this class of bug) is not done** — no test in `tests/`
> or elsewhere exercises the missing-tool path; a future PowerShell change to this script could
> silently reintroduce the same defect with nothing to catch it.
>
> **Requirement 3 is partially done.** The script itself now degrades gracefully when no `.venv`
> exists (`scripts/ci-local.ps1:135,141-143`: checks `Test-Path .venv`, warns, and falls back to
> whatever is on `PATH`) — verified on this machine, which genuinely has no `.venv` (tools live
> under `AppData\Local\Python\pythoncore-3.14-64\Scripts` instead). But `ONBOARDING.md` §1a's own
> documented invocation still reads `export PATH="$PWD/.venv/bin:$PATH"`, unchanged by `TASK-030`
> — still assumes a `.venv` this machine doesn't have. Not re-verified against whatever
> environment produced `TASK-030`'s "verified with a real run" claim, so this may be
> environment-specific rather than universally wrong; either way it wasn't re-checked.
>
> Scope narrowed to requirements 2 and 3 going forward; left in `backlog/` rather than closed,
> per `rules/design-discipline.md` — "prefer leaving something undone and named over done and
> wrong."

## Description

`pre_commit.ps1` gates every step on `$LASTEXITCODE`:

```powershell
Write-Host "`n[1/5] Ruff — lint" -ForegroundColor Cyan
ruff check sagittarius_engine tests
if ($LASTEXITCODE -ne 0) { Write-Host "Ruff lint failed!" -ForegroundColor Red; exit $LASTEXITCODE }
```

`$LASTEXITCODE` is only ever *set* by a native executable actually running. When PowerShell
cannot resolve `ruff`/`mypy`/`pytest` on `PATH` at all, that is a non-terminating shell-level
error ("the term '...' is not recognized...") — no process starts, and `$LASTEXITCODE` simply
keeps whatever value it already held (0, or unset, in a fresh session). The `if` check then
sees no failure, and the script proceeds through all 5 steps to print:

```
========================================
 All local checks passed successfully!
========================================
```

with an exit code of 0 — while nothing was actually linted, type-checked, or tested.

## How it was found

Found 2026-08-23 running the gate for `TASK-026` on this machine, following
`ONBOARDING.md` §1a's documented invocation
(`export PATH="$PWD/.venv/bin:$PATH"; pwsh ./pre_commit.ps1`). This machine has no `.venv` —
`ruff`/`mypy`/`pytest` live under
`C:\Users\<user>\AppData\Local\Python\pythoncore-3.14-64\Scripts` instead — so every one of the
5 steps failed to resolve its command, and the script still reported full success. Re-running
with the correct `PATH` surfaced the real, expected state (pre-existing mypy debt, see
`TASK-021`).

This is not a one-off PATH mistake specific to this session or this machine. It is a structural
gap: **any** invocation where the required tools are not already resolvable on `PATH` before
`pre_commit.ps1` starts gets this exact silent false-positive, with no error, warning, or
distinguishing output versus a genuine all-green run. Given `ONBOARDING.md` §1a calls this
script "the actual, authoritative local CI gate," a gate that can silently lie about having run
at all is a serious integrity gap — see `rules/surprising-findings.md`'s "success indicators
that lie" category, and the `--show`/`offscreen` precedent it documents.

## Requirements

1. Make the script fail loudly, not silently, when a required tool is missing. Options, in
   order of robustness:
   - Check each tool resolves (`Get-Command ruff -ErrorAction Stop`, etc.) before running the
     checks, with a clear error naming which tool and where it looked.
   - Or: set `$ErrorActionPreference = "Stop"` (or equivalent per-command `-ErrorAction Stop`)
     so an unresolvable command is a terminating error the script cannot silently step over.
   - Either way, a command-not-found must produce a nonzero exit and a message that says *that*
     — not the same red text as a real lint/type/test failure, and never the green success
     banner.
2. Add a regression test/check for this class of bug: temporarily shadow one tool (e.g. rename
   `PATH` to exclude it) and assert the script exits nonzero and does not print the success
   banner. A PowerShell-level test (Pester) or a small wrapper script both work; pick whichever
   fits the repo's existing tooling.
3. Once fixed, re-verify `.agents/rules/testing.md` / `ONBOARDING.md` §1a's own example
   invocation actually works as documented against this repo's real toolchain location (no
   `.venv` exists here — confirm where CI/dev environments are expected to install `ruff`/
   `mypy`/`pytest`, and correct the documented `PATH` line if `.venv` is not actually how this
   repo is set up).

## Priority

~~**P1**~~ **P3** (downgraded 2026-08-23) — the P1-severity concern (the gate silently lying)
is the part now fixed and verified. What remains is closing the gap so it can't regress
unnoticed (requirement 2) and a small doc-accuracy check (requirement 3) — real, but no longer
urgent.

## Category

Build / Tooling — Completion Gate

## Related

- [TASK-021](TASK-021_ruff_config_shadowing.md) — the pre-existing mypy baseline this gate is
  supposed to be catching (and does, once `PATH` is correct).
- [TASK-026](../completed/TASK-026_validation_middleware_silently_self_disables.md) — the task
  during which this was found.
