# TASK-032: Triage and clear the remaining 23-error mypy baseline

## Description

Split out of `TASK-021` requirement 5 (2026-08-23) — that task closed the actual config bug
(a root `ruff.toml` shadowing `pyproject.toml`); this is the separate, larger cleanup it
uncovered and deliberately left out of scope. Keeping them apart matches
`Tasks/bug_report/README.md`'s own BUG-vs-TASK sizing principle: one task, one closeable unit
of work, not a config fix bundled with 27 unrelated type errors.

`scripts/ci-local.ps1` — the repo's real completion gate — has been failing at its mypy step
throughout tonight's whole work series. History: a `git stash` back to a clean `main` before
tonight's changes reported **28** errors; after `TASK-017`'s reliability hardening, **27**;
after `BUG-003`'s fix (2026-08-23, category 1 below — closed, not just filed), **23**. This task
now covers only what's left.

## The remaining 23, categorized (not a blanket `--ignore-missing-imports` widening — each needs its own look)

### 1. ~~Wrong `ILogger | None` annotation~~ — done, see `BUG-003` (was 4 errors)

Closed 2026-08-23: `kernel/dispatcher.py`'s and `kernel/bootstrap.py`'s `_get_logger()`
narrowed to `-> ILogger`, matching `IEngineContext.logger`'s guarantee. Also removed 6 dead
`if logger:` guards in `bootstrap.py` left over from when the type was (wrongly) optional. See
`Tasks/bug_report/completed/BUG-003_get_logger_annotation_contradicts_iengincontext_contract.md`
for the full account — kept for context, no action needed here.
Doing it will drop this baseline from 27 to 23 before the rest of this task even starts.

### 2. `StdLibContainer` generic return type (3 errors)

`infrastructure/container/std_container.py:187,199,247` — `Incompatible return value type (got
"object", expected "T")` at three `return concrete(...)` sites. The container resolves a class
dynamically and constructs it; mypy can't narrow the constructed instance back to the bound
`TypeVar` `T` without a cast or an `isinstance`-narrowed return. Needs a real fix (a `cast(T,
...)` at the boundary is defensible here — the container's own runtime logic already guarantees
the invariant mypy can't see — but confirm that logic before reaching for `cast`, don't add it
reflexively).

### 3. `base_presenter.py`'s `self.fsm` assigned three types across branches (3 errors)

`extensions/pyside_mvc/mvc/base_presenter.py:87,109,129` — `Cannot determine type of "fsm"`.
`__init__` assigns `self.fsm` to `DeclarativeStateMachine(...)`, `BaseStateMachine(...)`, or
`None` depending on which branch runs (`extensions/pyside_mvc/mvc/base_presenter.py:81-87`), with
no class-level annotation. Needs an explicit type: something like
`self.fsm: BaseStateMachine | None = None`, declared once before the branches, or a `Union` if
`DeclarativeStateMachine` and `BaseStateMachine` aren't already related by inheritance — check
which before picking.

### 4. `thread_affinity.py` — decorator/metaclass typing (3 errors + 1 note)

`extensions/pyside_mvc/safety/thread_affinity.py:81,96,118` — three distinct shapes:
- `:81`, `:96` — `attr-defined` on a wrapped callable (`_is_ui_mutator` / `_is_not_a_ui_mutator`
  set as dynamic attributes on a decorated function). Classic "stash metadata on a function
  object" pattern that mypy can't see without a `Protocol` or a `# type: ignore[attr-defined]`
  with a comment — decide which fits this codebase's existing convention.
- `:118` — `call-overload` on `type.__new__` — likely a metaclass or dynamic-class-creation
  pattern; needs the actual code read before proposing a fix, not guessed from the error alone.

### 5. `state_tokens.py:46` — dict unpacking with a narrower expected type (1 error)

`Unpacked dict entry 0 has incompatible type "dict[str, str | float]"; expected
"SupportsKeysAndGetItem[str, str]"` — a `**dict` spread where the source dict's values are
`str | float` but the target expects all-`str`. Likely a real, narrow type mismatch worth
checking for an actual bug (a numeric default token being merged where a string is expected)
before just widening the annotation.

### 6. `base_view.py:76` — `QEvent` has no `.child()` (1 error)

`"QEvent" has no attribute "child"` — `event.child()` is being called on a value typed as the
base `QEvent`, but `.child()` only exists on `QChildEvent`. Needs an `isinstance(event,
QChildEvent)` narrowing (or the parameter re-typed if the caller already guarantees it), not a
suppression — this one has a real narrowing fix available.

### 7. Test files (12 errors)

- `tests/extensions/pyside_mvc/test_overlay_host.py:71,88,91,107,122` (5) — `Item "None" of
  "X | None" has no attribute ...`, same `union-attr` shape as category 1; check whether these
  are testing the same over-widened annotations `BUG-003` fixes, or a separate case.
- `tests/extensions/pyside_mvc/test_thread_affinity.py:49,50` (2) — `Incompatible types in
  assignment (expression has type "int", variable has type "None")`.
- `tests/extensions/fsm/test_declarative_state_machine.py:307,308` (4) — `Argument 2 to
  "on_enter" ... incompatible type` + `"append" of "list" does not return a value` — a lambda
  returning a tuple `(order.append(2), fsm.dispatch(...))` used where a `Callable[[], None]` is
  expected. Real code smell (relying on `list.append`'s `None` return inside a tuple-comma
  trick) worth fixing properly, not suppressing.
- `tests/runtime/tasks/test_exclusive_action.py:186` (1) — `Need type annotation` — a bare
  `= []` or `= {}` mypy can't infer; add the annotation.

## Requirements

1. Fix `BUG-003` first (separate, already-scoped bug) — re-measure the baseline afterward
   (expect 23).
2. Work through categories 2–7 above, each as its own small, reviewable change — not one giant
   diff. A real fix per site; `# type: ignore` only where category 4 calls it out as a candidate,
   and only with a comment explaining why.
3. After each category, re-run `mypy sagittarius_engine tests --ignore-missing-imports
   --follow-imports=skip` and confirm the count drops by exactly that category's error count —
   an unexpected residual means the fix didn't fully address the site.
4. When this reaches 0, remove the `--ignore-missing-imports` allowance from `scripts/ci-local.ps1`
   and `.github/workflows/ci.yml` if it's no longer needed for a real reason (it may still be —
   check what it's currently masking before dropping it), and update
   `.agents/ONBOARDING.md` §1a's "known current state" note, which still says "~27 pre-existing
   errors."
5. `.agents/context/lint.md` still documents "the known 27 mypy errors" in its mypy section
   (added alongside `TASK-021`'s ruff fix) — update once this task closes, per that file's own
   forward-reference.

## Explicitly out of scope

- Toolchain version pinning (local `ruff`/`mypy` vs CI's pinned versions) — stays in `TASK-021`,
  it's a config/process problem, not a type-error cleanup.
- Linting `examples/`/`tools/` in CI — stays in `TASK-021`, unrelated axis.

## Priority

P3 — no runtime impact (every one of these 27 is a type-checker gap, not an observed defect;
categories 2, 5, and 6 are the only ones with a plausible *real* bug underneath, and even those
are unconfirmed). Real cost is that the completion gate has been red for this reason across
every task closed tonight, which normalizes ignoring a red gate — worth fixing for that reason
alone, not urgency.

## Category

Kernel / Typing / Tech Debt

## Related

- `TASK-021` — where this was originally requirement 5; now split out.
- `BUG-003` — the 4-error subset with an already-written fix; do this one first.
