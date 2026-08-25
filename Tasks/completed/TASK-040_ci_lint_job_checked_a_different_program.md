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

---

## What the unblocked jobs then exposed

Unblocking `lint` was necessary but not sufficient: the five jobs came back and immediately
reported three further defects, none of which could have been seen while they were skipped.
Each is recorded here rather than in a new task, because each is the *same* defect this task is
about — CI checking something other than what it claimed to check — and none was visible until
this task's fix landed.

### 3. Every Linux job needed the Qt libraries, not just the Import Guard

`pytest-qt` imports Qt during `pytest_configure`, so the `test` job died on the same
`libEGL.so.1` error as the guard — before collecting a single test. Rather than repeat the
`apt-get` block in five places, the install moved into a composite action,
`.github/actions/qt-system-libs/action.yml` (`if: runner.os == 'Linux'`), used by `test`,
`architecture`, `examples`, `benchmark` and `import-guard`. `QT_QPA_PLATFORM: offscreen` is set
once at workflow level: every runner here is headless, and `offscreen` is a real plugin on
Windows too, so one declaration covers the whole matrix.

### 4. A duplicate `env:` key silently invalidated the entire workflow

Adding that workflow-level `env:` as a *second* top-level `env:` block produced a run with
**zero jobs and conclusion `failure`** — GitHub rejects the file outright. The local check that
was supposed to catch this did not: `yaml.safe_load` accepts duplicate mapping keys and keeps
the last one, so the workflow parsed clean locally while being invalid to the thing that
actually runs it.

Fixed by merging into the existing block, and re-verified with a loader that *rejects*
duplicate keys instead of silently resolving them. A validator more permissive than the
consumer is not a validator — the same shape of fault as a linter checking a different program.

### 5. A test that could never pass in CI: `test_agents_docs_resolve.py`

With `test` finally running, exactly one test failed, on both `ubuntu-latest` and
`windows-latest`:

```
FAILED tests/test_agents_docs_resolve.py::test_staleness_check_actually_catches_the_original_bug
  - subprocess.CalledProcessError: Command '['git', 'show', '0bd461b:.agents/context/repository.md']'
    returned non-zero exit status 128
1 failed, 1260 passed, 7 skipped -- coverage 90.72% (threshold 80%, passed)
```

The test reads the pre-fix text of `.agents/context/repository.md` out of commit `0bd461b`
(2026-08-02) and re-runs the staleness checker over it, proving the checker flags
`Sagittarius_ForkBoy` — a bug that really sat undetected for three weeks. Reading it from git,
rather than from a fixture someone wrote to make the test pass, *is* the test's argument.

`actions/checkout@v4` clones with `fetch-depth: 1`. That commit is not in a depth-1 clone, so
`git show` exits 128 and the assertions are never reached — the test could only ever fail in
CI, from the day it was written. It went unnoticed for the ordinary reason: this job was
skipped, not run.

Fixed with `fetch-depth: 0` on the `test` job's checkout only. That is the sole job running the
whole `tests/` tree; the others name single files that never shell out to git. The cost is
measured, not assumed: 794 commits, 2.77 MiB packed.

The alternative — vendoring the old blob as a fixture — was rejected. It would remove the git
dependency, but a committed copy is a copy: the test would then assert that the checker agrees
with a file in this repository, which is the exact thing the test was written to be stronger
than.

#### Verified both directions

| Clone | `0bd461b` present | `pytest tests/test_agents_docs_resolve.py` |
|---|---|---|
| `git clone --depth 1` (CI's default) | no | `1 failed, 1 passed` — CI's error, exactly |
| `git clone` (what `fetch-depth: 0` gives) | yes | `2 passed` |

Full suite on Python 3.12 with CI's own command
(`pytest tests/ examples/student_management/tests/ --cov-fail-under=80`): **1258 passed, 8
skipped**, coverage 90.69%.

#### Not a defect: the QML `Theme is null` output

The `test` job's log tail is flooded with hundreds of
`TypeError: Cannot read property 'accent' of null` lines from `DateTimePicker.qml`,
`AppDataTable.qml` and others. They are emitted at interpreter shutdown, *after* the pytest
summary, and they fail nothing — the same lines appear on a fully green local run. They are
noise that buries the one line that matters, which is why this failure looked like a QML
problem for as long as it did. `BUG-006` already covers the QML warning tests; this is not
that, and nothing here was changed for it.
