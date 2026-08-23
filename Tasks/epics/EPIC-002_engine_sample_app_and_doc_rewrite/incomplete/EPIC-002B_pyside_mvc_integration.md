# EPIC-002B — Full `pyside_mvc` Integration

**Epic:** [EPIC-002 — Engine Sample App & Doc Rewrite](../README.md)
**Status:** 🔵 Backlog
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

## 📐 Design Constraints

- No `sagittarius_engine/` source changes — see `ONBOARDING.md` §3.5. If `pyside_mvc` cannot
  be booted as an `IExtension` at all without an engine change, stop, write up exactly what's
  missing, and flag it to the user rather than patching the engine mid-subtask.
- Every screen still must pass the existing static guards (anti-literal-colour,
  anti-raw-primitive, rectangle-as-card, gallery-coverage, import-boundary) — a sample that
  violates the engine's own rules is worse than no sample.

## 🧪 Verification & Test Coverage

- The app boots, the UI renders, `pyside_mvc` lifecycle (register/boot/shutdown) is
  demonstrably invoked through the real `IExtension` path — not asserted, shown (e.g. a log
  line or test asserting the extension's `boot()` ran).
- `qInstallMessageHandler`-style check for QML runtime warnings on startup, following the
  precedent in `test_gallery_emits_no_qml_runtime_warnings` — `QQuickWidget.errors()` alone
  is known to miss runtime binding failures (see `design-discipline.md`'s table).
- A written account (feeds directly into EPIC-002C) of: what the `IExtension` boot path
  required that wasn't obvious, any ordering workaround needed, and any widget-kit gap hit.
