---
name: Commit Rules
description: Guidelines for committing and pushing code.
trigger: model_decision
---

# Rules: Commit

## CI/CD Validation
Before committing and pushing code, you MUST ensure that the local CI/CD pipeline passes completely.
Always run `scripts/ci-local.ps1` and fix any issues before proceeding with a commit. See
`.agents/ONBOARDING.md` §1a for exact invocation and how to read its output.

## Architectural Integrity
Ensure that commits do not violate Clean Architecture boundaries. A commit should never introduce
a concrete infrastructure dependency (e.g., SQLAlchemy, a network SDK) into `sagittarius_engine/domain/`,
`sagittarius_engine/interfaces/`, or `sagittarius_engine/kernel/` — see `rules/architecture.md`'s
"Engine Package Layout" for the full per-package dependency rules.
