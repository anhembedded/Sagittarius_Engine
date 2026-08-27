# ♻️ Refix Board — `REF-XXX`

Convention adopted 2026-08-27. A **refix** is a *reconciliation*: two things in this
repository disagree, and the work is deciding which one yields and then making them agree.

## Why this is not the Bug Board and not a Task

`Tasks/README.md`'s existing rule of thumb:

> **BUG** = something is wrong or states something untrue; **TASK** = something is missing or
> should change.

Both presume one side is at fault. A refix is the case where that is not obvious up front:

| | Presumes | Work is |
| :--- | :--- | :--- |
| **BUG** | behaviour is wrong | making it right |
| **TASK** | something is missing | building it |
| **REF** | two artifacts disagree | deciding which yields, then aligning both |

`REF-001` is the shape: `code-rule.md` §45 said function-local imports are never allowed and
the engine had thirty-two of them. Filing that as a bug presumes the code is wrong; filing it
as a task presumes the rule is. It was neither — nine were correct and the rule was too
absolute, twelve were unjustified and the code was wrong, and eleven were unproven either
way. Only a document that starts from "these two disagree" gets to that answer.

## Rule of thumb

Reach for `REF` when **fixing one side without deciding about the other would be wrong**:

- a written rule contradicts shipped code
- a document's links contradict the filesystem
- two ID pools, two schemas, or two naming conventions collide
- a comment claims a reason the code no longer has

Everything else is still a `BUG` or a `TASK`. Do not use `REF` to soften a defect: if
behaviour is wrong, it is a bug.

## Layout

```text
Tasks/refix/
├── README.md          # This file — the register below
├── incomplete/        # REF-XXX not yet reconciled
└── completed/         # REF-XXX reconciled, with evidence
```

`REF-XXX` is its own incrementing pool, independent of `TASK` / `EPIC` / `BUG`.

**A refix is not done until both sides agree and something enforces it.** A reconciliation
that rests on everyone remembering the decision has not been made — it has been described.
`REF-001`'s guard test is the standard.

## Register

| ID | Reconciles | Status |
| :--- | :--- | :--- |
| **[REF-001](completed/REF-001_function_local_imports_rule_vs_code.md)** | `code-rule.md` §45 ("never") vs. 32 function-local imports in the engine | ✅ Done 2026-08-27 |
| **[REF-002](incomplete/REF-002_stale_backlog_links_after_task_moves.md)** | `Tasks/` documents linking into `backlog/` vs. files that now live in `completed/` | 🟠 Open |
| **[REF-003](incomplete/REF-003_epic_007_id_collision_across_repos.md)** | `EPIC-007A..F` cited in 8 documents meaning Elite Warrior's epic vs. this repo's own `EPIC-007` | 🟠 Open |
