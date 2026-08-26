# BUG-006 — The two "no QML runtime warnings" tests police the whole Qt message stream, so they fail or pass depending on test order

**Reported date:** 2026-08-25
**Severity:** Medium (a gate test whose result depends on collection order — it can both block a clean change and hide a real regression)
**Status:** 🟠 Partially fixed 2026-08-26 — the platform-warning half is closed (see
§Decision); the Linux teardown half is **still open**, so this file stays in `incomplete/`.
**Found by:** `EPIC-008C`, while A/B-verifying that an event-bus change had not broken anything

---

## What is wrong

Two tests capture Qt's message stream and assert it is completely empty:

- `tests/extensions/pyside_mvc/test_widget_kit_gallery.py::test_gallery_emits_no_qml_runtime_warnings`
- `examples/student_management/tests/presentation/roster/test_roster_screen.py::test_roster_screen_emits_no_qml_runtime_warnings`

Both do `assert messages == []` over **every** `QtWarningMsg`/`QtCriticalMsg`/`QtFatalMsg`,
not just warnings originating from QML. On this machine Qt emits a platform warning the first
time a font database is initialised in a process:

```text
QFontDatabase: Cannot find font directory
C:/.../Sagittarius_Engine/.venv/Lib/site-packages/PySide6/lib/fonts.
Note that Qt no longer ships fonts. Deploy some (...) or switch to fontconfig.
```

That warning is emitted **once per process**, so it lands on whichever of the two tests happens
to have its message handler installed at that moment — which is decided by collection order,
not by anything either test is trying to verify.

## Reproduction — deterministic, not flaky

```bash
# gallery first: gallery fails, roster passes
pytest tests/extensions/pyside_mvc/test_widget_kit_gallery.py \
       examples/student_management/tests/presentation/roster/test_roster_screen.py -q
#   1 failed, 18 passed

# roster first: BOTH pass
pytest examples/student_management/tests/presentation/roster/test_roster_screen.py \
       tests/extensions/pyside_mvc/test_widget_kit_gallery.py -q
#   19 passed
```

Same two files, same code, opposite results. Nothing about the QML under test changed.

This is also why adding unrelated tests changes the failure count of the full suite: during
`EPIC-008C` the suite went from 1 failure to 2 purely because new test files shifted collection
order, and both times the message was this same font warning — no QML binding was involved
either time.

## Second contaminant, found on Linux 2026-08-25 (during `EPIC-007A`)

The font warning above is Windows-specific — its own reproduction paths are `C:/...`, and on
Linux neither order in the block above fails (`19 passed` both ways). **The ordering
sensitivity still reproduces there**, with a different message: QML `TypeError` warnings from
`RosterScreen.qml` itself.

```text
RosterScreen.qml:87:  TypeError: Cannot read property 'averageGpa' of null
RosterScreen.qml:82:  TypeError: Cannot read property 'totalStudents' of null
RosterScreen.qml:133: TypeError: Cannot read property 'students' of null
   ... 32 of them
```

These come from bindings re-evaluating against a root context object that is already gone, at
**process teardown**. In a clean run all 32 land after pytest's own summary line, where nothing
is listening:

```text
line 244:  971 passed, 8 skipped, 10 warnings in 23.86s
line 483:  file://.../RosterScreen.qml:87: TypeError: Cannot read property 'averageGpa' of null
```

Adding four unrelated test files under `tests/extensions/pyside_mvc/widgets/overlays/` shifted
teardown timing enough that some arrived *inside* `test_roster_screen_emits_no_qml_runtime_warnings`'s
message handler, failing it. Editing one of those new tests shifted it back to green. The test
passes in isolation in every case.

Two consequences for the fix in Requirements below:

1. **Option 2 ("make the environment not produce the platform warning") no longer closes this
   bug.** It addresses the font warning only; this contaminant is emitted by the app's own QML
   during teardown and would survive it.
2. This is a **false negative** in the sense §"Why this matters" describes, and a live one: the
   suite has been green on Linux only because these 32 warnings happen to land after the
   summary. Any change that shifts teardown timing flips it, so a green result here says
   nothing about whether the QML is clean.

Worth checking separately whether the 32 teardown `TypeError`s are themselves a defect in
`RosterScreen.qml`'s bindings (a `null` root context guard) rather than only noise — that is
not this bug, but nobody has looked.

## Worse than order-dependent: it is non-deterministic — measured 2026-08-25

The title says "order-dependent", which implies a fixed order gives a fixed
answer. It does not. Three consecutive full-suite runs, **same commit, same
command, same collection order, nothing else running**:

```text
run 1:  1 failed, 1141 passed, 8 skipped   in 17.60s
run 2:  1142 passed,           8 skipped   in 17.49s
run 3:  1142 passed,           8 skipped   in 17.74s
```

The failing run was `test_roster_screen_emits_no_qml_runtime_warnings`,
carrying the same `RosterScreen.qml` teardown `TypeError`s described above.
In isolation it passes every time.

This was found while trying to attribute a failure to a commit that changed
**only a docstring** — 15 lines of comment in `widgets/guards.py`, which
cannot reach QML at all. The suite happened to be green on the parent commit
and red on the child, which reads exactly like a regression and is not one.

Consequences that make this worth more than its Medium severity suggests:

1. **A green suite is not evidence for this test.** It passes ~2 runs in 3,
   so any change can be "verified" against it by luck.
2. **A red suite invites a false attribution.** The natural next step —
   bisect, blame the diff — costs a session and finds nothing, because the
   diff is innocent. That happened here; only re-running the same commit
   three times settled it.
3. **CI reports on one run.** With ~1-in-3 failure it will go red on
   unrelated pull requests, and the cheapest response for whoever hits it is
   to re-run until green, which trains everyone to ignore this test.

Whatever fix is chosen from Requirements below, it should be judged by
running the full suite **several times on the same commit**, not once.

## Why this matters beyond the noise

The tests were written for a good reason, documented in their own docstrings:
`QQuickWidget.errors()` reports only *parse* errors, and a binding that throws at evaluation is
a runtime warning it never sees — capturing the message stream is what caught a real defect
(every card's compact badge rendering blank) that four passing tests had missed. That value is
real and must not be lost.

But as written, the guard is unreliable in both directions:

- **False positive:** a platform warning that has nothing to do with QML fails the gate, which
  trains readers to dismiss this test's failures — exactly what happened here across several
  sessions before the mechanism was pinned down.
- **False negative:** if the font warning lands on the *other* test, the one that gets it
  "used up" now has an empty message list, and a genuine QML binding warning arriving later in
  the same test would still be caught — but the ordering sensitivity means neither test's green
  result is trustworthy on its own.

## Requirements

1. **Do not fix this by loosening the assertion to "ignore warnings we don't like".** Narrowing
   what a guard inspects to make it pass is the failure mode `design-discipline.md` names
   explicitly. Any narrowing must be justified by what the test is *for* — QML-attributable
   warnings — not by which strings are currently inconvenient.
2. Decide and record which of these is the fix:
   - assert only on warnings attributable to QML (the handler receives a `QMessageLogContext`
     with `file`/`category`; a QML binding warning carries a `.qml` source), or
   - make the environment not produce the platform warning (deploy the fonts Qt no longer
     ships, or set an explicit font configuration for the test session), or
   - install the message handler for the whole test session in a fixture so a once-per-process
     platform warning is consumed in a known place rather than by whichever test runs first.
3. Whichever is chosen, add a test that fails if the ordering sensitivity comes back — e.g. the
   two commands above must give the same result in both orders.
4. `pwsh ./scripts/ci-local.ps1` green — paste the `===CI_LOCAL_RESULT===` block and the log path.

## Decision (2026-08-26) — requirement 2, recorded

**Chosen: option (a), assert only on warnings attributable to QML.** A predicate
`_is_qml_attributable(context, message)` treats a message as in-scope when `context.file` ends
in `.qml` or the text carries Qt's `…/Foo.qml:87:` prefix. Applied to both tests named above.

Against requirement 1 — this is narrowing, so it needs a justification beyond "the failing
string is inconvenient". The justification is the tests' own subject: both are named *no **QML**
runtime warnings* and exist because `QQuickWidget.errors()` misses bindings that throw at
runtime. `QFontDatabase: Cannot find font directory …` is a statement about the machine's font
deployment. It is not a QML binding, cannot be the defect these guard against, and Qt emits it
once per process — so it lands on whichever test holds the handler at that moment, which
collection order decides.

Options (b) and (c) were not taken: this file already records that (b) "no longer closes this
bug", and (c) is the right tool for the teardown half below, which is not what was fixed here.

### What this closes, and what it does not

Closes: the `windows-latest` failure of `test_gallery_emits_no_qml_runtime_warnings`, which is
the font warning and nothing else.

**Does not close:** the Linux half. The 32 `RosterScreen.qml` teardown `TypeError`s are
`.qml`-attributable, so they still pass the predicate. Anything that shifts teardown timing can
still land them inside a handler. That needs option (c) (a session-scoped handler) or the
null-guard question this file already raises about `RosterScreen.qml`'s bindings — and until one
of those is done, a green run here still is not strong evidence.

### Requirement 3, deliberately not satisfied as written

Requirement 3 asks for a test that fails if the ordering sensitivity returns — "the two commands
must give the same result in both orders". That test is **not** added, because option (a) does
not close the teardown half: an ordering test would be a knowingly flaky test, which is what
this bug is about in the first place. Adding one would be theatre.

Instead the *mechanism* is locked in deterministically, in
`tests/extensions/pyside_mvc/test_widget_kit_gallery.py`:
`test_the_platform_font_warning_is_not_treated_as_a_qml_warning` (the verbatim message from
§"What is wrong") and `test_a_real_qml_binding_warning_is_still_caught` (narrowing must not
blind the guard to the `TypeError: Cannot read property 'showIcon' of null` defect it was
written for). Requirement 3 comes back into force with whoever fixes the teardown half.

### Verification

Both orders from §Reproduction: 21 passed each way. Full suite three consecutive times on the
same commit, as §"Worse than order-dependent" requires: **1359 passed, 8 skipped** every run.

Requirement 4 (`pwsh ./scripts/ci-local.ps1`) was **not** run — no `pwsh` in this environment.

## Note on a separate, unrelated intermittent failure

`tests/test_agents_docs_resolve.py`'s two tests also fail intermittently, but for a different
reason and only when the suite is launched through `scripts/ci-local.ps1` under PowerShell:
that test shells out to `grep`, which is not on `PATH` in that context
(`FileNotFoundError: [WinError 2]`). Same class of problem as `TASK-028`. Not covered by this
bug; filed here only so the two are not conflated again.

---

## Further evidence (2026-08-25, `TASK-040`)

Two points the original report could not establish, both measured while getting the `test` job
running again:

**It is not Windows-only, and not tied to `ci-local.ps1`.** It reproduces on Linux under plain
`pytest`, in this container, with `QT_QPA_PLATFORM=offscreen`.

**It is nondeterministic run-to-run, not merely order-dependent.** The *same* command — CI's
own `pytest tests/ examples/student_management/tests/ --cov=sagittarius_engine
--cov-fail-under=80 -q` — run twice in a row, unchanged tree, gave:

| Run | Result |
|---|---|
| 1 | `1258 passed, 8 skipped` |
| 2 | `1 failed, 1257 passed, 8 skipped` — `test_roster_screen_emits_no_qml_runtime_warnings` |

Run in isolation the same file is `7 passed`. So the trigger is not collection order alone,
which is stable between identical invocations; something run-to-run variable (hash seed,
font-database initialisation timing) decides which test's handler is installed when the
once-per-process platform warning is emitted.

This strengthens requirement 3: an ordering-only regression test — running the two commands in
both orders — would **not** have caught this, because both orders can pass. The fix needs to
remove the dependency on *when* the warning is emitted (requirement 2's second or third
option), not just pin the order.

**Not observed in GitHub Actions CI yet.** The run that finally exercised this job
(`5dbdccd`) reported only the `0bd461b` shallow-clone failure; both QML warning tests passed
there. That is luck, not immunity — the same coin-flip applies on the runner.
