---
name: Design Discipline
description: This is a reusable engine — decisions follow the design, root causes get fixed, and workarounds are never the answer. Always applies.
trigger: always_on
---

# Rules: Design Discipline

> Context: Sagittarius Engine is a **library with consumers**, not an
> application. A shortcut taken here does not stay here — it ships, gets
> imported, and becomes permanent debt inside somebody else's codebase,
> where they cannot fix it. An application can carry a hack until someone
> gets around to it. A reusable engine cannot.

---

## The rule

**Every change follows from the design. Fix the cause, not the symptom.**

Concretely, in order:

1. **Find the actual cause.** A change that makes a symptom disappear
   without an explanation of *why* it disappeared is not a fix — it is a
   coincidence that will be trusted as a fix.
2. **Check it against the written rules** (`architecture.md`,
   `ui-architecture.md`, this file). If the correct fix contradicts a rule,
   then either the rule is wrong or the design is — resolve *that*, in the
   rule file, as its own change. Never route around a rule silently.
3. **Only then write the code.**

## What a workaround looks like

All four are real, from 2026-08-23, and in each the shortcut was available
and rejected:

| Symptom | The shortcut | What was done instead |
| :--- | :--- | :--- |
| `BaseCard`'s `implicitWidth` binding self-referenced | Patch the expression until the loop stops | Recognised it violated the rule that regions own geometry (`ui-architecture.md` §4); removed the responsibility from the component entirely |
| A Python model embedded in QML resolved null | Keep the two `x ? x.y : default` guards — it worked | The guards *were* the symptom; reverted to a screen-level ViewModel, the mechanism that needs none |
| `--show` opened no window | Tell the user to unset `QT_QPA_PLATFORM` | Fixed the script forcing `offscreen` at import before argv was read |
| A null binding, hypothesis: an `_`-prefixed id | Rename it, confirm it works, move on | Tested the hypothesis — it was wrong; renaming would have entered a false cause into the permanent record |

The last one matters most. **"It works now" is not a diagnosis.** A fix
whose stated cause is wrong is worse than no fix: it teaches the next
reader something untrue, and the real cause is still live.

## Debt is allowed — silently is not

Carrying a compromise is sometimes correct. Doing it invisibly never is. A
compromise must be:

1. **Named** where it lives — a comment at the exact line, not a paragraph
   in a file nobody opens.
2. **Justified** with the real reason, including what would be required to
   remove it.
3. **Bounded** so it cannot spread — ideally by an automated guard, not by
   intention.

The reference case is the two backward-compatibility shims
(`base_view.py`, `QmlShared/log_list_model.py`): each carries a
`DeprecationWarning`, each is listed explicitly in
`import_boundary.SANCTIONED_DEEP_IMPORTS`, and the guard fails on any *new*
deep import. The debt is visible, explained, and cannot grow.

Contrast with an unmarked `x ? x.y : default`, which looks like ordinary
defensive code to every future reader and quietly normalises the hazard it
is hiding.

## Applies equally to the agent's own work

- **Do not close a task by weakening its acceptance criteria.** If a
  criterion cannot be met, say so and leave the task open. How that failure
  looks in practice: four `BOT-098F*` tasks in the consuming app were once
  moved into `completed/` while their own `Status:` lines still read
  *In Progress* — the move was never a sign-off, just a file operation. A
  later session caught the mismatch, found the stated proof requirements
  genuinely unmet, and moved all four back; they sit in `in_progress/`
  today (verified 2026-08-23).
- **Do not soften a test to make it pass.** A test changed to accommodate
  broken behaviour converts a detector into a rubber stamp.
- **Prefer leaving something undone and named over done and wrong.** An
  honest gap is scheduleable; a wrong implementation with a passing test is
  invisible until it costs someone a day.
