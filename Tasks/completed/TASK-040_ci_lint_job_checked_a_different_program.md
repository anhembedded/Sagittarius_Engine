# TASK-040: The lint job type-checked a different program than the one the tests run

- **Status**: ✅ Completed
- **Completion Date**: 2026-08-25
- **Priority**: P1 — main's CI had been red on every run for days, and a red gate teaches people to ignore gates
- **Category**: CI / Build

---

## Description

Two CI jobs had been failing on **every run on `main`**, going back to at least 2026-08-23, and
neither had anything to do with the changes that kept landing on top of them.

### 1. `Lint & Type Check` — mypy, on a program that does not exist

The job installed `requirements-dev.txt` **only**. That file has no `PySide6`, so mypy resolved
every Qt type to `Any`, and:

```
thread_affinity.py:124: error: No overload variant of "__new__" of "type"
matches argument type "type[Any]"  [call-overload]
        instance = cls.__new__(cls)
```

`cls.__new__(cls)` is fine when `cls` is a `type[QObject]`. It has no matching overload when
`cls` is `type[Any]`.

**Checking without the runtime dependencies is weaker checking, not stricter** — and here it
manufactured a defect in correct code. The `test` job has always installed both requirements
files. The gap between the two jobs was the whole bug: the linter was checking a different
program than the one the tests ran.

Reproduced both directions, in a venv built to match the job exactly:

| Environment | Result |
| :--- | :--- |
| `requirements-dev.txt` only | `Found 1 error in 1 file (checked 436 source files)` — the CI failure, exactly |
| plus `requirements.txt` | `Success: no issues found in 436 source files` |

### 2. `Package Import Guard` — a system library, not a code defect

```
ImportError: libEGL.so.1: cannot open shared object file: No such file or directory
```

PySide6 links against the system EGL/GL stack, and a bare GitHub runner has none of it, so
importing `pyside_mvc.mvc.base_view` from the installed wheel failed. The guard has been red
since it was added in `49c941b`.

## Why this mattered more than two red jobs

Every other job `needs: lint`. With lint red, **five jobs were skipped on every run**: `test`,
`architecture`, `examples`, `benchmark`, `package`. The test suite has not run in CI for days.

That is the exact failure `scripts/verify_wheel_importable.py` was written about, in its own
docstring:

> *"Every downstream job `needs:` the lint job, so once lint went red the test suite and the
> package check never ran at all. The failure that would have been loudest was the one
> silenced."*

The guard was built to survive that trap — and the trap then closed on everything else,
including `EPIC-006E`'s new `sagittarius-doctor` gate, which lives in the skipped `examples`
job and had therefore never run in CI at all.

## What was done

- **Lint job installs `requirements.txt` as well.** mypy now sees the types the code actually
  has. Costs install time; buys a type check of the real program.
- **Import Guard installs the system libraries PySide6 links against** — `libegl1`, `libgl1`,
  `libglib2.0-0`, `libxkbcommon0`, `libdbus-1-3`.

  Installing them rather than exempting the Qt modules, deliberately: that script's own
  docstring says an exemption list "should be a deliberate, argued change rather than a quiet
  append", and exempting Qt would blind the guard to the largest package in the wheel.

## Still red, and not addressed here

**`Security Audit` — Bandit findings.** Not a one-line environment fix: the findings need
reading, and each is either a real issue or a justified `# nosec`. That is its own task, with
its own judgement calls, and bundling it into a CI-environment fix would have hidden it.

It does not gate anything — `Security Audit` has no dependents — so the five skipped jobs come
back regardless.

## Verification

`ruff check`, `ruff format --check` and `mypy` all clean over CI's exact scope
(`sagittarius_engine tests examples tools`), run from a venv built the way the fixed job builds
one. The `libEGL` half cannot be verified locally — this container has the libraries installed
already — so it is confirmed by the CI run on the branch rather than asserted.

## Related

- `49c941b` / `TASK-039` — the import guard this repairs
- `TASK-021` — added `examples/` and `tools/` to the lint scope; the missing runtime deps
  predate it
- `EPIC-006E` — its CI gate was among the five silently skipped
