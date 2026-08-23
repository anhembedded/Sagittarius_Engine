---
name: Coding Style
description: General coding style guidelines, SOLID principles, and structural rules.
trigger: model_decision
---

# Rules: Coding Style

> Context: Absolute constraints. Apply to ALL generated code. Readability > Cleverness.

## 1. Strict Bans

* **NO Zombie Code:** Delete unused or commented-out code.
* **NO Lazy TODOs:** Implement fully. No `// TODO` or `// FIXME`.
* **NO Magic Values:** Extract hardcoded numbers and strings to `CONSTANTS`.
* **NO Clever One-Liners:** Avoid heavily chained methods or deep comprehensions.

## 2. Clean Code (KISS, YAGNI, DRY)

* **Single Target:** Functions and classes must do ONE thing only.
* **DRY:** Extract duplicated logic into shared helpers immediately.
* **YAGNI:** Implement strictly what is requested. Zero speculative over-engineering.
* **Immutability First:** Prefer immutable variables and pure functions where applicable.

## 3. SOLID Principles

* **SRP:** One reason to change per class/module.
* **OCP:** Open for extension, closed for modification. Use composition over modification.
* **LSP:** Subclasses must be fully substitutable for their base classes.
* **ISP:** Segregate large interfaces into smaller, client-specific ones.
* **DIP:** Depend on abstractions. Explicitly inject dependencies; do NOT instantiate inside.

## 4. Naming

* **Variables:** Descriptive names. NO single-letter variables (except loop indices).
* **Consistency:** Strictly follow the surrounding file's naming convention.
* **Functions:** Prefix with strong verbs (e.g., `fetch`, `calculate`).
* **Booleans:** Prefix with `is`, `has`, `can`, or `should`.

## 5. Structure

* **Early Returns:** Use the Bouncer Pattern. Handle errors first and return immediately.
* **Max Nesting:** Do not exceed 3 levels of indentation. Extract to helpers if deeper.
* **Vertical Grouping:** Use blank lines to group related logical blocks.

## 6. Comments

* **Explain "Why", not "What":** NO syntax or obvious operation comments.
* **Docstrings:** Required for public APIs, classes, and complex functions.

## 7. Idiomatic & Native

* **Idiomatic:** Write language-specific best practices.
* **Standard Library First:** Prefer built-in functions over custom implementations.

## 8. Observability

* **NO Function Call Side Effects:** NEVER execute state-mutating functions, DB queries, or API calls directly inside a logger statement.
* **Strict Separation:** Resolve operations to local variables first, then log the variables.

## 9. Run lint & CI

* refer: [Lint context](../context/lint.md)
* **Local CI/CD:** Always run `scripts/ci-local.ps1` to validate code formatting and pass tests before committing changes.

## 10. Architectural Consistency
* **Strict Layering:** Respect the 4 Clean Architecture layers. The Core (Domain & Application) must be completely isolated from Adapters (Presentation) and Infrastructure.
