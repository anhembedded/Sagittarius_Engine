# Contributing to Sagittarius Engine

Thank you for your interest in contributing to **Sagittarius Engine**! We welcome contributions from the community.

---

## 🚀 How to Contribute

### 1. Branch Strategy
- Main branch: `main` (production-ready releases)
- Development branch: `develop` (active development target)
- Feature branches: `feature/short-description`
- Bugfix branches: `fix/short-description`

### 2. Development Setup
```bash
# Clone the repository
git clone https://github.com/anhembedded/Sagittarius-Engine.git
cd Sagittarius-Engine

# Install in editable mode with dev dependencies
pip install -e .[dev]
```

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
2. Open a Pull Request targeting `develop`.
3. Provide a clear PR description detailing:
   - What changed
   - Why the change is needed
   - How it was tested
4. Ensure CI checks pass.

Thank you for helping make Sagittarius Engine better!
