# Contributing to Sagittarius Engine

Thank you for your interest in contributing to **Sagittarius Engine**! We welcome contributions from the community.

---

## 🚀 How to Contribute

### 1. Branch Strategy
- Main branch: `main` — **the integration target.** Open pull requests against it.
- Feature branches: `feature/short-description`
- Bugfix branches: `fix/short-description`

> A `develop` branch was listed here as "the active development target" until 2026-08-25.
> **It does not exist** — `git ls-remote --heads origin develop` returns nothing, and every
> merged pull request to date targets `main`. A contributor following this file would have
> opened their PR against a branch that is not there.

### 2. Development Setup
```bash
# Clone the repository
git clone https://github.com/anhembedded/Sagittarius-Engine.git
cd Sagittarius-Engine

# Install in editable mode, plus the dev toolchain
pip install -e .
pip install -r requirements-dev.txt
```

> This said `pip install -e .[dev]` until 2026-08-25. There is no `dev` extra —
> `[project.optional-dependencies]` declares only `audit` — so pip printed
> `WARNING: sagittarius-engine 2.3.0 does not provide the extra 'dev'`, installed nothing
> extra, and **exited 0**. Anyone following this file got no pytest, no ruff and no mypy, with
> no error to tell them. The pinned toolchain lives in `requirements-dev.txt`.

### 3. Code Style & Standards
- Python **3.12+** syntax.
- Follow Clean Architecture principles:
  - Domain = Python standard library only (no external dependencies).
  - Interfaces in `sagittarius_engine/interfaces/`.
  - Type hints on all public functions and methods.
- Format code using `ruff`:
  ```bash
  ruff check .
  ruff format .
  ```

### 4. Testing Requirements
Before submitting a Pull Request, ensure the full test suite passes:
```bash
# Run test suite
pytest

# Verify test coverage
pytest --cov=sagittarius_engine
```

### 5. Documentation
If your changes affect public APIs or runtime behaviors:
- Update docstrings (`@brief`, `@param`, `@details`).
- Update the relevant files under `.agents/context/` — that is this repo's documentation; there
  is no separate `docs/`/MkDocs site (`BUG-002`).

---

## 📬 Submitting a Pull Request

1. Push your branch to GitHub.
2. Open a Pull Request targeting `main`.
3. Provide a clear PR description detailing:
   - What changed
   - Why the change is needed
   - How it was tested
4. Ensure CI checks pass.

Thank you for helping make Sagittarius Engine better!
