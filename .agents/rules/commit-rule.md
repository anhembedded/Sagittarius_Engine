---
name: Commit Rules
description: Guidelines for committing and pushing code.
trigger: model_decision
---

# Rules: Commit

## CI/CD Validation
Before committing and pushing code related to the Binance Bot, you MUST ensure that the local CI/CD pipeline passes completely.
Always run `Sagittarius_Elite_Warrior\scripts\ci-local.ps1` and fix any issues before proceeding with a commit.

## Architectural Integrity
Ensure that commits do not violate Clean Architecture boundaries. A commit should never introduce an Infrastructure dependency (e.g., SQLAlchemy, network SDKs, sagittarius_engine) into the Domain or Application layers.
