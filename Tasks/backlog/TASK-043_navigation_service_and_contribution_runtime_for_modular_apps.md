# TASK-043: Navigation service, contribution runtime and boundary tooling for modular (bounded-context) consumer apps

- **Status**: 🔵 Backlog
- **Category**: UI Engine / Composition Runtime (`pyside_mvc`) + Core Architecture
- **Priority**: P2 — first real consumer identified; not needed before that consumer's Phase 5
- **Filed by**: consumer app `Sagittarius_Elite_Warrior` — `PRO-004` / `EPIC-025` (HLD `Docs/HLD/05_engine_app_split.md`), 2026-09-11
- **Belongs to**: [`EPIC-001D — Runtime, Regions & Slot Registry`](../epics/EPIC-001_ui_engine_foundation/incomplete/EPIC-001D_runtime_slot_registry.md). This task is the **concrete, consumer-driven slice** of that epic, not a parallel design.

---

## 🎯 Summary & Objectives

The reference consumer is splitting itself into bounded-context modules, each a real `IExtension`,
with screens that are pure *composition surfaces* of widgets the modules contribute. The engine's
own rule (`.agents/rules/ui-architecture.md` §1) says the **Runtime** layer — *"Shell, regions,
navigation, screen lifecycle"* — is engine-owned. Today the engine offers only `PresenterManager`
(lazy `QStackedWidget` routing) and nothing above it; the consumer has bridged the gap with its own
`ScreenRegistry` (`EPIC-016` on its side) and will build a `IContributionRegistry` as app policy.

This task gives the engine the **mechanism** those app-side pieces should stand on, so the second
consumer app does not rebuild them. The consumer's decision record is explicit about the split:
**engine owns mechanism, app owns policy** (which contribution *kinds* exist, which module list,
which surface is gated by which config key — all stay app-side).

Objectives, in priority order — each is independently shippable:

1. **`NavigationService`** on top of `PresenterManager`: `navigate(route, *, source: NavigationSource)`
   where `NavigationSource` distinguishes `USER_INTENT` from `RESTORE`. Rationale from the consumer:
   its `BUG-104`/`BUG-107` — restoring the last route on startup silently triggered the screen's
   side-effects (auto-sync, opening a live websocket). A restore must never be indistinguishable
   from a click. Plus a `can_leave()` hook so a screen with an in-flight background action can veto
   or finish before navigation (`async-ui-action-rule` §1 on the consumer side).
2. **Slot/contribution registry** as *mechanism*: a contribution is a frozen descriptor + factory,
   keyed by `(surface_id, slot, kind)`, exposed **as a model per slot** (EPIC-001D constraint:
   "registry state is exposed as models, not dynamically-named context properties"). The engine
   does **not** know which kinds exist — `kind` is an opaque string the app registers. Ordering,
   add/remove/reorder survive; a contribution whose factory raises fails the surface loudly.
3. **`create_quick_widget(..., import_paths: Sequence[str] = ())`**: today `_QML_IMPORT_PATH` is the
   single hard-coded path for `Sagittarius/UI`. Per-widget extra import paths let a consumer module
   ship its own QML next to its Python without a `QQmlApplicationEngine` (none exists repo-wide,
   deliberately). Consumer's ADR D6 is deferred on exactly this.
4. **Generalise `import_boundary.py`**: `find_deep_imports()` only checks imports reaching past the
   `pyside_mvc` re-export surface. The consumer needs the same AST machinery for its own rules
   (`modules/X` may import only `modules/Y/contracts`), with a **shrink-only allowlist** (ratchet).
   Proposed shape: `find_cross_package_imports(root, rules: Sequence[BoundaryRule], allowlist)`,
   where a rule is `(from_package_glob, allowed_import_globs)`. Keep `find_deep_imports` as a thin
   caller of it.
5. The UI runtime becomes a real `IExtension` (already decided in EPIC-001D on 2026-08-23; the
   ordering question is answered by `examples/student_management/docs/ui_extension_lifecycle.md`:
   construct `QApplication` before `App.boot()`, no engine change needed).

## 📐 Design Constraints

- Honour every EPIC-001D constraint verbatim: Python describes, QML renders; registry is for
  genuinely dynamic surfaces; the runtime must not know the consuming application; regions decide
  geometry.
- No new module concept. Contributions are made by ordinary `IExtension`s in `boot()`; the
  consumer's `BoundedContextModule` base stays on its side (promote only when a second consumer
  needs the identical shape — `architecture-rule` §6.3 spirit).
- Every public symbol this task adds goes into `sagittarius_engine.extensions.pyside_mvc.__all__`
  and is a `b` bump per `release.md` §2 ("published API changed"). The consumer declares each one in
  its `engine_capabilities.py` (`RequiredEngineCapability`) so a stale build fails with the
  reinstall command instead of an `AttributeError` deep in a widget constructor.
- Known engine gaps the consumer measured and that this task should **not** silently paper over
  (file separately if they turn out to matter): `StdLibContainer.bind()/singleton()` overwrite
  silently (only `registrations()` exists for introspection); `ExtensionManager.register()` treats
  `optional_dependencies` as blocking at that stage; `Scheduler` has no per-job cancel.

## 🧪 Verification & Test Coverage

- `NavigationService`: a route restored with `source=RESTORE` reaches the presenter with that source
  visible; a `can_leave()` returning `False` blocks `navigate()`; unknown route still raises.
- Registry: contributions render into the declared slot in declared order; add/remove/reorder
  reflected in the per-slot model; a raising factory fails the surface, not the app.
- `create_quick_widget(import_paths=...)`: a QML file importing a module found only via the extra
  path loads; without the path it fails the same way it does today.
- `find_cross_package_imports`: fixture tree with one allowed and one forbidden import; allowlist
  that is stale (lists a non-violation) fails the ratchet.
- No new sanity-tier tests on the consumer side are required by this task (its `testing-rule` §1).

## 🔗 Consumer-side references (read-only, for context)

- `Sagittarius_Elite_Warrior/Docs/HLD/README.md` (§4 contribution points, §5 engine/app split).
- `Sagittarius_Elite_Warrior/Tasks/epics/EPIC-025_module_theo_bounded_context/DECISION_2026-09-11_module_boundaries.md` (D3, D6, D10, O2).
