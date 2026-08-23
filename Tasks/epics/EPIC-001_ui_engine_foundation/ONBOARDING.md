# Onboarding — EPIC-001: UI Engine Foundation

**Read this file first, before any other file in this epic directory.** It exists because
an AI session with no memory of prior conversations needs to reach the same starting point
a human would after being briefed — this document is that briefing.

---

## 1. What problem this solves, in one paragraph

`Sagittarius_Elite_Warrior` (the Binance trading bot app, a separate repo that depends on
this engine) has 4 screens, each built independently with its own hosting model, its own
styling, its own hand-rolled widgets. Measured evidence (2026-08-22): **342 hardcoded colour
literals across 97 distinct values in the app's QML**, against an official palette of 14
tokens — including two different "gold" hex values nobody intended to create, because there
was nothing stopping a second one from being typed. The fix is not a cleanup pass; a cleanup
pass would drift again the same way. The fix is a UI Engine that makes the wrong thing
**impossible to do**, not merely discouraged — see §3 for why that specific framing matters.

## 2. Read in this order

| Order | File | Why |
| :---: | :--- | :--- |
| 1 | This file | Orientation — you are here |
| 2 | [`README.md`](README.md) (this epic's own) | Full context, measured evidence, the 4-subtask breakdown, what's explicitly out of scope |
| 3 | [`../../../.agents/rules/ui-architecture.md`](../../../.agents/rules/ui-architecture.md) | The binding rule this epic exists to satisfy. Every subtask's deliverable is judged against this file. |
| 4 | The relevant subtask file (`completed/` or `incomplete/`) | Your actual work item |
| 5 | `../../../.agents/ONBOARDING.md` | Standard engine-repo entry point — context/rule routing, general engineering process. Load *after* the above, not instead of it — this epic has enough specific context that the generic routing table alone will miss it. Renamed from `PLAYBOOK.md`/`manifest.yml` 2026-08-23. |

Do not skip to step 4. The rule in step 3 encodes decisions (§3 below) that look arbitrary
without the reasoning in step 2 — an agent that starts at the subtask file alone tends to
"simplify" those decisions back into the exact drift this epic exists to stop.

## 3. Decisions already made — do not re-derive or relitigate these

These were reached after real back-and-forth with the user (a solution architect, not a UI
specialist) and are now settled. If a design question in your subtask seems to reopen one of
these, it almost certainly doesn't — re-read `ui-architecture.md` first.

1. **Three-layer ownership: Tokens → Widget Kit → Runtime.** The engine owns every visual
   value, every widget, and the screen shell/lifecycle. The consuming app owns domain
   vocabulary and composition only. This is deliberately **structural**, not a style guide —
   a convention living in the app's own `components/` folder was tried implicitly and it
   drifted (see §1's numbers). Something the app cannot import around is what actually holds.
2. **Grows `pyside_mvc` in place.** No parallel/second UI extension. `pyside_mvc` already
   has real, working pieces (`BasePresenter`, `BaseView`, `PresenterManager`, `OverlayHost`,
   the `Theme` bridge, 7 `QmlShared` components) — this epic is upgrading and completing
   that extension, not building a green-field replacement next to it.
3. **Escape hatch = single-level inheritance from an engine base primitive**, never a bare
   `Rectangle`/`Item`. Full reasoning in `ui-architecture.md` §1.1. The short version: a
   framework with no sanctioned way to do something non-standard gets bypassed through an
   *unsanctioned* one, and the unsanctioned bypass is what reintroduces drift. Permitting a
   controlled escape — one that still inherits token-driven visuals — keeps escapes visible
   and grep-able instead of invisible.
4. **Token vocabulary is fixed and engine-owned; the app fills values, not names.** Reverses
   today's `get_theme_bridge()`, which accepts an arbitrary dict with no engine opinion on
   keys. Necessary precondition for engine-side "did the app supply every required token"
   validation — you cannot validate a vocabulary you don't own.
5. **Sequencing is Tokens → Kit → Runtime, deliberately, even though Runtime (the
   slot-registry/plugin-style composition model) is the most conceptually interesting part.**
   Runtime is also the most speculative layer — it requires knowing which widgets exist and
   which surfaces are genuinely dynamic, which isn't reliably known until the layers under it
   are real. Building it first means designing its abstractions with the least information
   available. Tokens first because they're cheap, lock in nothing, and pay off immediately.

## 4. Current state (check this is still accurate before trusting it)

As of 2026-08-23: **`EPIC-001A`/`EPIC-001B`/`EPIC-001C` are all done.** `EPIC-001C` (Widget
Kit Expansion) shipped `AppDataTable`, `AppModal`, `Gallery`, card **compact mode** +
`CardModel`, a `scripts/show-gallery.ps1` runner (real window or headless PNG), and **four**
static guards: anti-literal-colour, anti-raw-primitive, `Rectangle`-as-styled-card, and
gallery coverage. `C`'s own §5 documents the same-day increment and — more usefully — two
mistakes worth not repeating: an attempt to embed a `CardModel` QObject in every card's QML
tree that hit three QML init-order hazards **without failing a single test**, and a
`--show` mode that could never open a window because offscreen was forced at module import.
Both are why `test_gallery_emits_no_qml_runtime_warnings` now captures Qt's message stream
instead of trusting `QQuickWidget.errors()`, which sees parse errors only.

Two small items remain deliberately deferred inside `C`'s own file (not blocking):
`DateTimePicker.qml`'s calendar popup was not retrofitted onto `AppModal`, and no icon-only
button variant exists yet. One known defect is recorded but unfixed: `LogPanel` throws in its
`ListView` delegate when a second instance exists, regardless of model contents.

**`EPIC-001D` (Runtime/Registry) is unblocked but not started — and has an open design
question that must be settled first** (its objective 5): does the UI Engine become a real
`IExtension`/`IModule` of Sagittarius Engine, or stay deliberately outside it? Today it is
outside — `configure_app_qml()` is a bare function call after `app_engine.boot()` has already
finished — which means `app_engine.shutdown()` has no path to the `Theme` singleton or
`OverlayHost`. Decide before building the shell's lifecycle contract, not after.

Verify this is still true rather than trusting this document indefinitely:

```bash
ls Tasks/epics/EPIC-001_ui_engine_foundation/completed/
ls Tasks/epics/EPIC-001_ui_engine_foundation/incomplete/
```

Whichever subtask has the lowest letter in `incomplete/` is the next one to pick up, unless
the user directs otherwise — dependency order is strictly `A → B → C → D` (stated in the
epic `README.md` §4).

## 5. Cross-repo boundary — a real trap, not a formality

This engine repo (`Sagittarius_Engine`) and the consuming app repo
(`Sagittarius_Elite_Warrior`) are **two independent git repos**, nested on disk but no
longer submodule-linked. They have:

- separate task boards (this repo's `Tasks/README.md` vs. the app's `Tasks/ROADMAP.md`) —
  **never write an app-side task into this repo's board or vice versa**,
- separate `.agents/` rule sets — the app's `qml-rule.md` was this epic's reference material
  for *quality and structure*, but its actual content is app-specific and does not apply
  here verbatim,
- an installation gap that blocks live iteration: the app currently installs this engine
  **non-editable from GitHub**, pinned to a specific commit. An engine change made in this
  repo is invisible to the app until that pin is switched to an editable local install
  (`install-rule.md` Option 2) or the change is pushed and the app reinstalls. If your
  subtask needs to verify behaviour from the app's side, check this first — otherwise you
  will edit this repo and wonder why nothing changed in the app.

Nothing in `EPIC-001B/C/D` should touch app code. If a subtask seems to require an app-side
change, stop and flag it — that almost certainly belongs on the app's own board as part of
its (separately tracked, not-yet-started) migration epic, not here.

## 6. How to know you're actually done, not just done-looking

Every subtask file has its own `Verification & Test Coverage` checklist — satisfy that one
specifically. But the standing test for the *epic as a whole*, restated from the epic
`README.md`, is worth keeping in view for any subtask:

> Change one token — accent colour, corner radius, spacing scale. Count how many consumer
> app files must change to stay visually correct. The answer must be zero.

If your change makes that number go up instead of down, something is wrong even if your
subtask's own checklist passes.

## 7. If you get stuck or a decision genuinely isn't covered above

Say so explicitly rather than guessing and moving on — this user has stated directly (and
it's recorded as standing project guidance) that **incorrect assumptions are worse than
incomplete work**, and that pushback on a bad or ambiguous instruction is expected, not
optional. Silently picking an interpretation and proceeding is the wrong default here.
