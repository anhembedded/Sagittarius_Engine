# Build & CI/CD Pipeline

The project uses modern Python packaging — `pyproject.toml` only. (Corrected 2026-08-23: the
previous version of this file also claimed a `setup.py`; there isn't one, and hasn't been.)

## Development Commands

* **Install Dependencies**: 
  ```bash
  pip install -r requirements.txt
  pip install -r requirements-dev.txt
  ```
* **Install Project locally (Editable mode)**: 
  ```bash
  pip install -e .
  ```
* **Linting & Formatting (Ruff)**: 
  ```bash
  ruff check sagittarius_engine tests
  ruff format sagittarius_engine tests
  ```
* **Type Checking (Mypy)**: 
  ```bash
  mypy sagittarius_engine tests --ignore-missing-imports --follow-imports=skip
  ```
* **Run Tests & Coverage (Pytest)**: 
  ```bash
  pytest tests/ --cov=sagittarius_engine --cov-report=term-missing --cov-fail-under=80
  ```

## CI/CD Workflow (GitHub Actions)

Defined in `.github/workflows/ci.yml`. It runs automatically on PRs and merges to `main` / `develop`.

### Pipeline Jobs

Seven jobs, verified against `ci.yml` on 2026-08-23 (the previous version of this list omitted
`benchmark` entirely):

1. **Lint & Type Check** — fails fast if Ruff or Mypy catches issues.
2. **Test Matrix** — Pytest across OSs (Linux, Windows) and Python versions (including
   3.14-dev). Minimum 80% coverage enforced (`--cov-fail-under=80`).
3. **Architecture Guard** — runs `tests/test_architecture.py` so core boundaries can't be
   violated.
4. **Example Integration** — runs `tests/test_examples.py`, so a framework change that breaks
   user-space apps fails here.
5. **Performance Benchmark** — ⚠️ **currently broken and silently so.** It runs
   `tests/benchmark_runtime.py`, a path that moved to `tests/runtime/benchmark_runtime.py` in
   commit `843137a`; the step has errored ever since. The job declares
   `continue-on-error: true`, so the pipeline still goes green and no benchmark has actually
   run since that reorganization. Tracked as
   [TASK-020](../../Tasks/backlog/TASK-020_ci_benchmark_job_stale_path.md). Do not read a
   passing CI run as evidence that performance is unregressed.
6. **Security Audit** — `bandit` (SAST) and `pip-audit` (vulnerabilities).
7. **Package Build Check** — `python -m build` + `twine check` to validate distribution
   metadata.
