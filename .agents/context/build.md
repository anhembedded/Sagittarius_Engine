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
5. **Performance Benchmark** — runs `tests/runtime/benchmark_runtime.py` (path corrected
   2026-08-23, `TASK-020`; it had silently pointed at `tests/benchmark_runtime.py`, moved away
   in commit `843137a`, since that reorganization). `continue-on-error: true` is kept
   deliberately — a timing-based benchmark on shared GitHub Actions runners is expected to be
   noisy, and failing the build on that noise would produce false-positive breaks unrelated to
   code correctness. That flag was not the actual cause of the months-long silent breakage
   (nobody was reading the job's output either way); it stays informational rather than gating.
6. **Security Audit** — `bandit` (SAST) and `pip-audit` (vulnerabilities).
7. **Package Build Check** — `python -m build` + `twine check` to validate distribution
   metadata.
