# AI Playbook

> Entry point for AI assistants working in this repository.

This document defines **how to work in this repository**, not **how the project is implemented**.

Project-specific knowledge lives under `.agents/context/`.

Engineering policies live under `.agents/rules/`.

Task workflows live under `.agents/skills/`.

---

# Core Principles

Always follow this execution order:

1. Understand the user's request.
2. Load the required project context.
3. Apply all relevant rules.
4. Select the appropriate engineering skill.
5. Execute the task.
6. Validate the result.

Never skip a step.

---

# Repository Layout

.agents/

    context/        Project knowledge

    rules/          Engineering policies

    skills/         Engineering workflows

    prompts/        Optional prompt templates

    workflows/      Long-form process write-ups

    anti-patterns/  Documented failure modes to avoid

---

# Context Routing

Load only the context required for the current task.

Always load:

- context/project.md
- context/repository.md

Additionally load:

| Task | Context |
|-------|---------|
| Feature Development | architectures/architecture.md, modules.md |
| Bug Fix | runtime.md, testing.md |
| Refactoring | architectures/architecture.md |
| Documentation | documentation.md |
| Deployment | deployment.md |
| Performance | runtime.md |
| API | api.md |
| Configuration | configuration.md |
| Build | build.md |

Do not load unrelated context.

---

# Rule Routing

Always apply:

- rules/architecture.md
- rules/coding-style.md
- rules/surprising-findings.md

Additionally apply:

| Task | Rules |
|------|-------|
| Testing | testing.md |
| Documentation | documentation.md |
| Commit | commit-rule.md |
| Deployment | deployment.md |
| Complex Multi-Phase Task | task-tracking.md |
| UI / QML (`pyside_mvc`) | ui-architecture.md |

Rules are mandatory.

Never violate project rules.

---

# Skill Routing

Every task must use one primary engineering skill.

| User Request | Primary Skill |
|--------------|---------------|
| Work a tracked task end to end | process_a_task.md |
| Locate/understand a module before changing it | module_discover.md |

If multiple skills are required:

- Choose one primary skill.
- Execute secondary skills afterward.

---

# Missing Context

Before asking the user:

Search the repository for:

- Existing implementations
- Tests
- Documentation
- Examples
- Configuration
- Build scripts
- CI workflows

Only ask questions if the required information cannot be found.

Never invent:

- APIs
- Configuration
- Business rules
- Runtime behavior
- File locations

Incorrect assumptions are worse than incomplete implementation.

---

# Multi-Step Tasks

If the request contains multiple independent tasks:

Execute them sequentially.

For each task:

1. Reload required context.
2. Apply relevant rules.
3. Execute the matching skill.
4. Validate.

Do not reuse assumptions across unrelated tasks.

---

# Validation

Before completing any task, verify:

- Correct context was used.
- Required rules were followed.
- Appropriate skill was applied.
- Tests updated if necessary.
- Documentation updated if necessary.
- No architecture violations exist.

---

# Completion

A task is complete only when:

- The user's request has been satisfied.
- Validation succeeds.
- Required deliverables are produced.
- Engineering quality has been preserved.

Never sacrifice correctness for speed.
