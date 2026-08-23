# EPIC-002B — Full `pyside_mvc` Integration

**Epic:** [EPIC-002 — Engine Sample App & Doc Rewrite](../README.md)
**Status:** ✅ Completed (2026-08-23)
**Category:** Documentation / Developer Experience / UI Engine
**Priority:** P1
**Depends on:** EPIC-002A (needs the backend to point a UI at)

---

## 🎯 Summary & Objectives

Give the sample app a real UI built entirely on `pyside_mvc` — tokens, widget kit, runtime,
`MVC`/`MVP` scaffolding, safety guards — and boot it as a real `IExtension`, per
[EPIC-001D](../../EPIC-001_ui_engine_foundation/incomplete/EPIC-001D_runtime_slot_registry.md)
§objective 5's decision (2026-08-23). This is the part of the plan most likely to surface real
friction — capturing that friction accurately is the actual deliverable, more than the UI
itself.

1. Boot `pyside_mvc` through the standard `IExtension.register`/`boot`/`shutdown` path, not
   `configure_app_qml()` as a bare function call after `app_engine.boot()`. If the ordering
   constraint noted in EPIC-001D (a `QApplication` must exist before `pyside_mvc` can boot)
   makes this awkward or impossible with the engine's current `IExtension` contract, **that
   is the single most important finding this subtask can produce** — record the exact point
   of friction, what was tried, and why it didn't fit, rather than quietly falling back to the
   old bare-call pattern.
2. Compose at least one screen using the widget kit's real components (`BaseCard` — both full
   and compact mode, `AppDataTable`, `AppModal`, `LogPanel` if the domain can justify a log
   view) — enough to exercise the token layer, the MVC/MVP wiring (`BasePresenter`/`BaseView`/
   `PresenterManager`), and the safety layer (thread affinity, UI watchdog) for real.
3. Follow `.agents/rules/ui-architecture.md` to the letter — this subtask is itself a test of
   whether that rule is sufficient and self-consistent for someone building a screen from
   scratch, not just retrofitting existing ones.
4. Do not add a new widget-kit component unless the sample genuinely needs one the kit lacks.
   If it does, that gap belongs in `AUDIT_REPORT.md`, not a same-session kit addition.
5. **Write `docs/ui_extension_lifecycle.md` the moment the `IExtension` boot ordering is
   settled** (see epic README's "Design docs" section) — this is the single highest-value
   design doc in the whole epic, since it's the first real resolution of the EPIC-001D
   ordering question. Sequence diagram showing exactly where `QApplication` construction, DI
   registration, and `pyside_mvc`'s `boot()` interleave. If token/theme wiring or screen
   composition turn out to be non-trivial too, they get their own docs the same way — don't
   wait until the subtask is "done" to write any of them.

## ⚠️ Resolve before starting: no `IExtension` wrapper exists for `pyside_mvc` yet

Checked 2026-08-23: `grep -rln IExtension sagittarius_engine/extensions/pyside_mvc/` returns
**nothing**, and [EPIC-001D](../../EPIC-001_ui_engine_foundation/incomplete/EPIC-001D_runtime_slot_registry.md)
— the epic that decided `pyside_mvc` *should* become one — is still `🔵 Backlog`, zero code.
Objective 1 below ("boot through the standard `IExtension` path") has nothing to boot
*through* yet. This is not friction to discover during the subtask — it's a fork to resolve
before writing any code, because the two branches land in different places:

- **Write the `IExtension` wrapper class as this sample app's own code**
  (`examples/student_management/infrastructure/pyside_mvc_extension.py` or similar) — a thin
  class implementing `register`/`boot`/`shutdown` that internally calls the existing
  `configure_app_qml()` (`runtime/qml_host_view.py:54`) at the right point. **This is the
  correct choice**: it satisfies "no engine source changes" (the wrapper lives in app code,
  not `sagittarius_engine/`), and it doubles as a real, running specification for what
  EPIC-001D's eventual engine-side class needs to do — far more useful to EPIC-001D than a
  design doc alone would be.
- ~~Add the class to `sagittarius_engine/extensions/pyside_mvc/` itself~~ — **do not do this.**
  That's real engine source code, contradicts this subtask's own "no engine changes"
  constraint, and would make EPIC-002B silently complete a chunk of EPIC-001D without that
  epic's own design questions (the shell, regions, registry) having been decided.

`docs/ui_extension_lifecycle.md` (objective 5) should document this app-side wrapper's real
behavior — and is exactly the artifact EPIC-001D should read first when it eventually builds
the engine-side version for real.

## 📐 Design Constraints

- No silent engine patches — see `ONBOARDING.md` §7. If `pyside_mvc` cannot be booted as an
  `IExtension` at all without an engine change, that is a **real gap, not a stopping point**:
  verify it, then file a `TASK-XXX` immediately per `ONBOARDING.md` §6 (flag to the user when
  filing it — this specific gap is large enough to need their sign-off on scope/timing, not
  just a notification). Do not fall back to `configure_app_qml()` to make the sample "work"
  in the meantime — an unfixed gap tracked in a task is honest; a silent fallback is not.
- Every screen still must pass the existing static guards (anti-literal-colour,
  anti-raw-primitive, rectangle-as-card, gallery-coverage, import-boundary) — a sample that
  violates the engine's own rules is worse than no sample.
- **`MODULE_COVERAGE.md`'s `pyside_mvc` row must resolve to Used, not Skipped.** Two prior
  sample apps in this repo (`student_management`, `tools/audit_dashboard`) both shipped a
  PySide6 UI without touching `pyside_mvc` — plain `QtWidgets` instead. That is the specific
  failure this subtask exists to not repeat.

## 🧪 Verification & Test Coverage

These are gates, not aspirations — do not mark this subtask done with any of them weakened:

- **The UI is built from `pyside_mvc`'s `Sagittarius/UI/` QML components, not `QtWidgets`.**
  Concretely checkable: the sample's screen files are `.qml`, loaded through
  `pyside_mvc.runtime`'s host view — not `QWidget` subclasses. A `grep` for
  `PySide6.QtWidgets` imports in the sample's presentation layer should turn up nothing
  beyond what hosting a `QQuickWidget` unavoidably requires.
- The app boots, the UI renders, `pyside_mvc` lifecycle (register/boot/shutdown) is
  demonstrably invoked through the real `IExtension` path — not asserted, shown (e.g. a log
  line or test asserting the extension's `boot()` ran).
- `qInstallMessageHandler`-style check for QML runtime warnings on startup, following the
  precedent in `test_gallery_emits_no_qml_runtime_warnings` — `QQuickWidget.errors()` alone
  is known to miss runtime binding failures (see `design-discipline.md`'s table).
- `MODULE_COVERAGE.md`'s `pyside_mvc` row is filled in with **Used** and a real file/line —
  this subtask does not close with that row still TBD.
- `docs/ui_extension_lifecycle.md` exists, has a Mermaid sequence diagram, and was written
  when the ordering was settled (per Objective 5) — not reconstructed after the fact.
- Any real engine gap hit has a filed `TASK-XXX`, linked from both this file's own notes and
  `MODULE_COVERAGE.md`'s `pyside_mvc` row if the gap is what blocked "Used."

---

## ✅ Completion notes (2026-08-23)

**Resolved: no engine gap.** The EPIC-001D ordering concern (a `QApplication` must exist
before `pyside_mvc` boots) resolves cleanly as long as the composition root (`gui.py`)
constructs `QApplication` before calling `App.boot()` — verified directly, no workaround
needed. `PySideMvcExtension` (app-side `IExtension` wrapper, since none exists in the engine
yet) is documented as a real prototype for `EPIC-001D` to build from — see
`docs/ui_extension_lifecycle.md`.

**Shipped:** `RosterScreen.qml` (real `AppDataTable`, `BaseCard` with a working compact-mode
toggle, `AppModal` enroll form), `RosterView`/`RosterPresenter`/`RosterViewModel`
(`QmlHostView`/`BasePresenter`/`BaseQmlViewModel`), `PySideMvcExtension`, `gui.py` entry point.
All 4 applicable static guards (literal-colour, raw-primitive, rectangle-as-card,
import-boundary) return zero findings. `presentation/` has exactly one `QtWidgets` import
(`QApplication` in `gui.py` — the unavoidable minimum). `MODULE_COVERAGE.md`'s `pyside_mvc`
row: **Used**.

**A significant investigation, and a real self-correction — worth reading in full in
`docs/ui_extension_lifecycle.md`'s last section.** Chasing "zero QML runtime warnings"
initially produced a false-positive engine bug report (`QmlHostView` reparenting before
`setSource()`), filed as a task and then **retracted** once a methodology error was found:
`tail`-truncated command output had been hiding pytest's own `N passed` verdict under a flood
of raw stderr the entire time. The tests had been passing throughout. The real, smaller,
still-true finding that survived scrutiny: `qInstallMessageHandler` — the technique this
codebase already trusts for catching silent QML failures — has a blind spot for QML JS engine
`TypeError`s that print directly to stderr, bypassing Qt's message-handler system entirely.
Not filed as an engine task (no actionable, confirmed root cause; zero functional impact —
final state is always correct); named and bounded in the design doc instead.
