# TASK-030: `pre_commit.ps1` doesn't capture logs or survive a truncated view

## Description

`pre_commit.ps1` (5 steps: ruff lint, ruff format, mypy, pytest+coverage, architecture tests)
has two real gaps, both of which `Sagittarius_Elite_Warrior/scripts/ci-local.ps1` already
solved:

1. **No log capture.** Output goes straight to the console. `context/testing.md` already
   documents the exact trap this creates — piping through `tail -N` can hide a real failure
   entirely, not just add noise — but nothing in the repo enforces it. The gate itself should
   make that trap unreachable, not just warn about it in prose.
2. **Stops at the first failing step.** `exit $LASTEXITCODE` on step 1 means a run that fails
   lint never learns whether mypy or the tests are also red. Discovering problems one gate-run
   at a time, instead of all at once, is slower for no benefit — confirmed directly on
   2026-08-23: running the gate found lint red, fixing it and rerunning found mypy also red
   (pre-existing, unrelated) — two runs to see what one run could have shown.

Also carries a live bug in its own text: the pytest step's `--ignore=tests/benchmark_runtime.py`
targets a path that hasn't existed since `843137a` (see `TASK-020`) — harmless today only
because pytest wouldn't collect that filename anyway, but wrong on its face.

## Requirements

1. Port `ci-local.ps1`'s two load-bearing patterns from Elite, not its Qt-parallel/sanity-tier
   machinery — Engine's suite is 750-ish tests at ~13s with no `xdist` dependency and only 4
   Qt-touching files; that complexity solves a problem Engine doesn't have.
   - Full-run transcript captured to `logs/ci-local-<timestamp>.log` plus a `logs/
     ci-local-latest.log` pointer, via `Start-Transcript`.
   - Every step runs regardless of earlier failures; failures accumulate in a list and are
     reported together at the end.
   - A machine-readable `===CI_LOCAL_RESULT===` block as the last thing printed — `RESULT`,
     `FAILED_STEPS`, `LOG_FILE`, and an explicit instruction not to trust console output alone
     without opening the log file. This is the direct fix for the truncation trap
     `context/testing.md` already names.
   - A post-test log scan for `- (WARNING|ERROR|CRITICAL) -` records (Engine's own log format,
     `std_logger.py`, matches Elite's exactly) — a green exit code from pytest is not proof the
     run was clean if something logged an ERROR mid-test and the assertion still happened to
     pass.
2. Fix the stale `tests/benchmark_runtime.py` path to `tests/runtime/benchmark_runtime.py`
   while rewriting the pytest step (closes the local-script half of `TASK-020`; the CI YAML
   half is separate).
3. Move to `scripts/ci-local.ps1`, matching Elite's location and name — a developer working
   both repos should be able to reach for the same command in either one. Update every
   reference to the old `pre_commit.ps1` path: `.agents/ONBOARDING.md`,
   `.agents/skills/process_a_task.md`, `TASK-021`.
4. Keep it right-sized: no native build step (Engine has none), no `-Workers`/parallel-worker
   flag (nothing to parallelize yet at this suite size — revisit if the suite grows enough to
   need it), no `-SanityOnly`/`-UnitOnly` (Engine's `tests/` mirrors package layout, not a
   sanity/unit/integration split).

## Priority

P2 — not a correctness bug, but the gap it closes is exactly the failure mode this repo's own
`context/testing.md` and `MEMORY.md` gate-verification rule both warn about; leaving it
unenforced after naming it twice is the kind of gap this repo's own audit exists to catch.

## Category

Build / Developer Experience

---

## ✅ Outcome — completed 2026-08-23

All four requirements done in one pass, verified with a real run.

- `scripts/ci-local.ps1` created: full-run transcript to `logs/ci-local-<timestamp>.log` +
  `logs/ci-local-latest.log`, all 5 steps run unconditionally (failures accumulate in `$failed`
  rather than stopping the script), post-test log scan for `- (WARNING|ERROR|CRITICAL) -`
  records, and the `===CI_LOCAL_RESULT===` machine-readable summary block as the last output.
- The stale `tests/benchmark_runtime.py` ignore path fixed to `tests/runtime/benchmark_runtime.py`.
- `pre_commit.ps1` deleted; `scripts/ci-local.ps1` matches Elite's name and location exactly.
  Three references updated: `.agents/ONBOARDING.md` §1a (rewritten, not just re-pointed —
  describes the new log-capture/full-run/summary behavior), `.agents/skills/process_a_task.md`,
  `TASK-021`.
- Deliberately did not port: native build step (none exists here), `-Workers`/parallel xdist
  (nothing to parallelize at ~750 tests / 13s), `-SanityOnly`/`-UnitOnly` (no sanity/unit split
  in this repo's `tests/` layout).

Verified with a real run: all 5 steps executed regardless of the known mypy failure (didn't
stop early), the log file was captured and is a real 392-line, 27-`error:` transcript matching
the known baseline, and the closing block correctly reported
`RESULT: FAIL` / `FAILED_STEPS: Mypy` — the one pre-existing, already-tracked failure, nothing
new.
