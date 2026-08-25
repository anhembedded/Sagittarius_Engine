# EPIC-006F — Runtime anomaly detection

**Epic:** [EPIC-006 — Wiring & Readiness Diagnostics](../README.md)
**Status:** ⏸️ Deferred — specify after `EPIC-006C` lands
**Category:** Diagnostics / Runtime
**Priority:** P3
**Depends on:** EPIC-006C

---

## Why this is deferred rather than backlogged

"Abnormal" is only definable relative to a settled baseline, and the engine has no concept of
settled until `EPIC-006C` defines one. Specifying the checks first would mean guessing at the
baseline they measure against, and every one of them would need rewriting once readiness exists.

Everything in `EPIC-006A`–`EPIC-006E` inspects **structure**, which holds still while you look
at it. This subtask is the first to watch **behaviour**, which does not — so it also inherits an
overhead question the others never had to answer.

## Candidate checks

- An event emitted with **zero handlers** — warn once, naming the emit site. Different from A1,
  which is static: this one fires only when something actually tries to publish into the void.
- A handler that **raised**. The bus no longer swallows these (`bde88e9`), so they can be counted
  and surfaced rather than merely logged.
- A task running **past an expected duration**; a hosted service that **died after starting**.

## The constraint that will shape it

Unlike every other subtask here, this one runs continuously. `EPIC-005` §4.2's overhead budget
becomes relevant, and the same rule applies: a diagnostic that perturbs what it measures is worse
than none.

Note the overlap with `EPIC-005` and resolve it deliberately rather than building both — a task
that ran too long is a question the trace recorder is better shaped to answer, and duplicating it
here would be the second implementation of the same idea.
