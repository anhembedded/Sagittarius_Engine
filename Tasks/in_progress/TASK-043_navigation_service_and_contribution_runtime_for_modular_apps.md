# TASK-043: Navigation service, contribution runtime and boundary tooling for modular (bounded-context) consumer apps

- **Status**: 🟡 In Progress — **E0 done 2026-09-19** (`ScheduledJob.cancel()`, §"How the consumer
  feeds this task" table below). E1–E3 not started: each is triggered by the consumer's own
  corresponding phase landing a stable, zero-app-import, ≥2-consumer version of the mechanism in
  its own tree first (the harvest pattern that table describes), not a fresh design built here.
  Consumer's Elite `EPIC-025` Phases 1–4 (which E1/E2 wait on) are done; Phase 5 (which E3 —
  `NavigationService` itself — waits on) has not started.
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
3. ~~**`create_quick_widget(..., import_paths: Sequence[str] = ())`**~~ — **dropped 2026-09-13.** The
   consumer decided (its ADR D20–D22) to build every module's UI in QtWidgets with the OS theme: no
   QML, no tokens. It keeps using `BaseView`, `BasePresenter`, `PresenterManager`, `QtEventBridge` and
   the thread-affinity helpers; it no longer calls `create_quick_widget`, `configure_app_qml` or
   the token layer. Whether this engine grows a QtWidgets kit is a separate decision the user has
   deferred; E2's region host below is a `QMainWindow`-based surface host. Original item, for the
   record: `create_quick_widget(..., import_paths: Sequence[str] = ())`: today `_QML_IMPORT_PATH` is the
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

## 🔁 How the consumer feeds this task — a harvest, not a design-first build (added 2026-09-13)

The consumer builds each mechanism inside its own tree first (`core/contracts/`,
`shell/workbench/`), with no application import and this engine's package layout, and **lifts**
it here once a written criterion holds: zero app imports, used by at least two surfaces or two
modules, API unchanged for one whole phase (consumer HLD §8). So this task is delivered in steps
that the consumer's phases trigger, not as one design:

| Step | Trigger (consumer) | Lands here |
| :-: | :--- | :--- |
| E0 | now | ✅ **Done 2026-09-19.** `ScheduledJob.cancel()` (`runtime/scheduler/scheduler.py`) — a `threading.Event`-backed flag, checked in `Scheduler._run()`'s per-tick evaluation and dropped the same way a dead (`next_run is None`) job already was. Two tests added to `tests/runtime/scheduler/test_scheduler.py` (a pending job cancelled before its first run never spawns; a recurring job cancelled after one run is not rescheduled for a second), mutation-verified against the real diff (`if job.is_cancelled:` forced to `if False:` made both fail for the right reason, then restored — `git diff` confirmed clean). Full local gate green: `ruff`/`mypy`/`bandit`/`pip-audit` clean, `1419 passed, 11 skipped` (full suite, including both new tests — confirmed collected under the gate's own invocation), architecture tests `14 passed`, log scan clean. `context/runtime.md`'s Scheduler section updated in the same change (`doc-code-sync.md`) |
| E1 | after its Phase 1 | `WorkbenchModule` (`IExtension` + `contribute` / `subscribe`), `ContributionRegistry`, `ContributionDescriptor`, `Place`, `SizeHint` → objectives 2 and 5. **Consumer's Phase 1 is done, but not yet harvested** — see the note added 2026-09-19 below the table |
| E2 | after its Phase 2 | the surface runtime: a region host with the place slots, per-place models (EPIC-001D objective 2). **Consumer's Phase 2 is done, but not yet harvested** — same note |
| E3 | with its Phase 5 | `NavigationService`, screen lifecycle + conformance suite, `create_quick_widget(import_paths=)` → objectives 1, 3, 5. **Consumer's Phase 5 has not started** (blocked on this very task, per its own `EPIC-025F`) — see the note below |

**Note added 2026-09-19, before attempting E1/E2/E3.** This task's own header says "start there, not
from a fresh design" — read literally, that means E1/E2 are not free to design from scratch here
just because the consumer's Phase 1/2 are done. The harvest criterion is specific: the consumer's
own tree must already hold a version of the mechanism that is (a) genuinely zero-app-import, (b)
used by at least two surfaces or two modules, and (c) API-unchanged for one whole phase — not
merely "the phase that would need it is finished." Whether Elite's own `IContributionRegistry`
(mentioned in its `EPIC-025F` task file, `shell/contribution_assembly.py`) already meets that bar
was not verified before this task file was updated; that verification, done from the consumer's
side by reading its actual code against these three criteria, is the concrete next step before any
E1 code is written here — not a re-derivation of the registry design from this repo's side. Filed
here rather than assumed, per `ONBOARDING.md` §9 ("say so and ask, rather than guessing").

**E3 is separately blocked, not just unstarted**: Elite's `EPIC-025F` names this task
(`TASK-043`/`EPIC-001D`) as its own blocker, in both directions — a genuine chicken-and-egg the
harvest table already resolves correctly: E3 is triggered *by* the consumer's Phase 5 landing a
working `NavigationService`-shaped mechanism in its own tree first (the same harvest pattern as
E1/E2), which Phase 5 cannot yet do because it currently has nothing but its own legacy
`ScreenRegistry` to build from. Untangling that either needs the consumer to prototype
`NavigationService` app-side against `ScreenRegistry`'s current shape (mirroring what
`examples/student_management/docs/ui_extension_lifecycle.md` already did for objective 5's
ordering question, §"Two lifecycles" above) or a user decision to build E3 here first, ahead of a
live consumer, as a deliberate exception to the harvest rule. Not decided in this session — surfaced
here for the user rather than guessed.

The consumer's SDD (`Docs/SDD/README.md`) already fixes the descriptor shape and the registry
validation rules that E1 will receive; read it before designing E1 independently.

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
