# TASK-020: CI benchmark job runs a path that no longer exists (silently)

## Description

`.github/workflows/ci.yml`'s `benchmark` job runs:

```yaml
- name: Run benchmarks
  run: PYTHONPATH=. python tests/benchmark_runtime.py    # ci.yml:176
```

That file was moved to `tests/runtime/benchmark_runtime.py` in commit `843137a`
("test: Reorganize tests directory to mirror source structure"). The workflow was never
updated, so the step has been failing with `can't open file` ever since.

**Nobody noticed because the job declares `continue-on-error: true`** (`ci.yml:158`). The
job goes green-with-a-warning, the pipeline passes, and no benchmark has actually run since
that reorganization.

A second, harmless-but-stale reference to the same old path sits at `ci.yml:85`, in the
`test` job's pytest args:

```yaml
--ignore=tests/benchmark_runtime.py
```

That `--ignore` is now a no-op. It happens not to matter — pytest wouldn't collect
`benchmark_runtime.py` anyway, since the name doesn't match the `test_*.py` pattern — but it
should move with the file rather than be left pointing at nothing.

Found on 2026-08-23 while re-verifying `.agents/context/build.md` against real CI config
(EPIC-002D). See that epic's `AUDIT_REPORT.md`.

## Requirements

1. Update `ci.yml:176` to `PYTHONPATH=. python tests/runtime/benchmark_runtime.py`.
2. Update or delete the stale `--ignore=tests/benchmark_runtime.py` at `ci.yml:85`.
3. Confirm the benchmark actually runs and produces output — it hasn't in CI since `843137a`,
   so it may have bit-rotted in other ways too (imports, moved engine APIs). Fix whatever
   surfaces.
4. **Decide, deliberately, whether `continue-on-error: true` should stay.** It is what let
   this hide for months. Either keep it and accept that benchmark breakage is invisible, or
   drop it and let a broken benchmark fail the build. Whichever is chosen, write the reason
   into `ci.yml` as a comment so the next reader doesn't have to re-derive it.
5. Update `.agents/context/build.md`'s pipeline-jobs list if any job's behaviour changes.

## Priority

P3 — nothing user-facing is broken, and the engine ships fine. But a CI job that has silently
not run for months is worse than no CI job, because the green check implies coverage that
isn't there.

## Category

CI / Build
