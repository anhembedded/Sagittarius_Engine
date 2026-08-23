---
name: Install & Environment Setup
description: How to set up and verify a dev environment for working inside the Sagittarius Engine repo itself.
trigger: always_on
---

# Sagittarius Engine — Dev Environment Setup Guidelines

All developers and AI assistants working **inside this repository** (`Sagittarius_Engine` —
developing the engine itself, not consuming it) MUST strictly follow these guidelines when
setting up or verifying the environment.

Corrected 2026-08-23: this file previously described installing `sagittarius_engine` as a
*dependency* of another project (`pip install git+https://.../Sagittarius-Engine.git`,
`.\scripts\run.ps1` / `run-ui.ps1`, `ci-local.ps1 -UnitOnly`) — Elite Warrior's content,
copy-pasted wholesale. None of those scripts or that installation model exist in this repo; you
cannot `pip install` this package into itself. That consumer-facing guidance belongs in
`readme.md`'s own Installation section (where it correctly already lives) and in the *consuming*
app's own `install-rule.md`, not here.

---

## 1. Setting up this repo for development

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .                   # editable install, so `import sagittarius_engine`
                                    # resolves to this working tree
```

## 2. Verification

Run the real local CI gate — never a hand-assembled subset of `pytest`/`ruff`/`mypy` on just the
files you touched, see `.agents/ONBOARDING.md` §1a for why:

```bash
export PATH="$PWD/.venv/bin:$PATH"
pwsh ./scripts/ci-local.ps1
```

---

## 3. Mandatory Rules for AI Agents & Automated Tools

1. **This repo is the engine, not a consumer of it.** Never add `sagittarius_engine` itself as
   a dependency in `requirements.txt`/`pyproject.toml`, and never suggest `pip install`-ing it
   from GitHub as a setup step for working *in* this repo — that instruction is for someone
   consuming the package, which is a different audience than this file.
2. **Do not leave the working tree dirty from environment setup.** No stray `.egg-info`,
   `__pycache__`, or build artifacts left staged or committed — `git status` clean after
   `pip install -e .`.
