# TASK-043: Navigation service, contribution runtime and boundary tooling for modular (bounded-context) consumer apps

- **Status**: 🟡 In Progress — **E0 done 2026-09-19** (`ScheduledJob.cancel()`), **E1 landed
  2026-09-19** (`ContributionDescriptor`, `SizeHint`, `SurfaceDeclaration`, `ContributionError`,
  `IContributionRegistry`, `ContributionRegistry` — §"How the consumer feeds this task" table
  below). E2–E3 not started: each is triggered by the consumer's own corresponding phase landing a
  stable, zero-app-import, ≥2-consumer version of the mechanism in its own tree first (the harvest
  pattern that table describes), not a fresh design built here. Consumer's Elite `EPIC-025` Phases
  1–4 (which E1/E2 wait on) are done; Phase 5 (which E3 — `NavigationService` itself — waits on)
  has not started.
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
| E1 | after its Phase 1 | ✅ **Landed 2026-09-19** (the slot/contribution registry half of objective 2; `WorkbenchModule`/navigation-side objective 5 stays with E3). `sagittarius_engine/extensions/pyside_mvc/runtime/`: `contribution_descriptor.py` (`ContributionDescriptor`, opaque-`str` `place`/`surface_id`), `size_hint.py` (`SizeHint`), `surface_declaration.py` (`SurfaceDeclaration` — narrower than Elite's own `Surface`: no `owner`/`gated_by`, YAGNI per the note below), `contribution_error.py` (`ContributionError`), `i_contribution_registry.py` (`IContributionRegistry`, a `Protocol`), `contribution_registry.py` (`ContributionRegistry` — mandatory `surfaces` constructor arg, no global-lookup default, the one gap the consumer's own registry still has). Exported from both `runtime/__init__.py` and `pyside_mvc/__init__.py`'s `__all__`. 11 tests in `tests/extensions/pyside_mvc/test_contribution_registry.py` covering `identity()`, all three `contribute()` raise paths, the success path, `panels()`'s stable sort, and `surface_declaration()`'s raise path; mutation-verified (each of the three raise-guards forced to `if False:` in turn, confirmed the matching test fails for the right reason, restored — `git diff --stat` clean). `ruff check`/`ruff format --check` clean; `mypy sagittarius_engine` clean (230 files); full `tests/extensions/pyside_mvc/` suite green (177 passed). See the note added 2026-09-19 below the table for the opaque-identifier design reasoning this landing follows |
| E2 | after its Phase 2 | the surface runtime: a region host with the place slots, per-place models (EPIC-001D objective 2). **Consumer's Phase 2 is done, but not yet harvested** — same note |
| E3 | with its Phase 5 | `NavigationService`, screen lifecycle + conformance suite, `create_quick_widget(import_paths=)` → objectives 1, 3, 5. **Consumer's Phase 5 has not started** (blocked on this very task, per its own `EPIC-025F`) — see the note below |

**Note added 2026-09-19, before attempting E1/E2/E3.** This task's own header says "start there, not
from a fresh design" — read literally, that means E1/E2 are not free to design from scratch here
just because the consumer's Phase 1/2 are done. The harvest criterion is specific: the consumer's
own tree must already hold a version of the mechanism that is (a) genuinely zero-app-import, (b)
used by at least two surfaces or two modules, and (c) API-unchanged for one whole phase — not
merely "the phase that would need it is finished."

**Verified 2026-09-19, by reading Elite's actual code, not assumed**: `src/core/contracts/
contribution_descriptor.py`, `place.py`, `size_hint.py`, `i_contribution_registry.py`, and
`src/shell/contribution_registry.py` (the implementation). Three of TASK-043's four named E1
pieces are strong matches, one needs a real redesign before it can move:

- **`ContributionDescriptor`** — a frozen dataclass (`contributor_id`, `surface_id`, `place`,
  `order`, `size_hint`, `factory: Callable[[IContainer], QWidget]`, `title`), plus an `identity()`
  uniqueness key. Genuinely stable since `PR 0.2` (2026-09-11 or earlier — this task's own filing
  date) through every phase since; used by every bounded context's `contribute()`, the shell's
  Welcome/Settings screens, and all four legacy screens — far past the "≥2" bar. `factory`'s
  `QWidget` reference is `TYPE_CHECKING`-only (the file's own docstring: "`core/` imports no
  toolkit at runtime"), so it is not a real Elite-app coupling, only a Qt one — no different from
  what this engine's own `pyside_mvc` already assumes. **Harvestable close to as-is.**
- **`SizeHint`** (`COMPACT`/`REGULAR`/`TALL`) — generic layout vocabulary, no Elite-specific
  member. **Harvestable as-is.**
- **The registry mechanism** (`ContributionRegistry` in `shell/contribution_registry.py`,
  `IContributionRegistry`/`IContributionTable` split, `contribute()`/`contribute_screen()`,
  identity-uniqueness enforcement, stable sort by `(order, contributor_id, factory qualname)`,
  gated-surface contributions silently dropped with one log line) — already close to
  harvest-shaped: its constructor takes `surfaces: dict[str, Surface] | None = None` as an
  **injectable** parameter, defaulting to Elite's own global `surfaces_by_id()` only when the
  caller passes nothing. The validation *behaviour* (raise on unknown surface/place, raise on
  duplicate identity, drop-with-a-log on a gated surface) is exactly what objective 2 describes as
  engine mechanism. **Harvestable, once `Surface` (below) stops being implicitly global.**
- **`Place`** (`Enum`: `SCREEN`/`HEADER`/`CONTEXT_BAR`/`WORKSPACE`/`RAIL`/`CONSOLE`/`MODAL`/
  `SETTINGS_SECTION`/`STATUS_TILE`/`DEV_PROBE`) is **not** harvestable as written, and this is a
  real finding, not a technicality: it is a **closed** `Enum` with Elite-specific members
  (`DEV_PROBE` is Elite's Dev Board; `SETTINGS_SECTION` is Elite's Settings surface shape) —
  exactly what objective 2's own text already warned against: *"The engine does **not** know which
  kinds exist — `kind` is an opaque string the app registers."* Lifting this `Enum` wholesale would
  bake one consumer's screen vocabulary into the engine, the same mistake `IStrategyCatalog` (an
  Elite-internal example, different repo, same shape) was built and then deleted for. The correct
  harvest is **not** "copy this enum" — it is: the engine's own `ContributionDescriptor`/registry
  take `place` (and, by the same argument, `surface_id`) as an **opaque string** (or an
  `Enum`-like `Protocol`/`NewType`, not a fixed closed set), and Elite's own `Place` `Enum` stays
  entirely app-side, its members becoming the concrete opaque values Elite happens to pass through
  that slot. `SizeHint`'s three buckets read as more genuinely universal (any composition surface
  needs "how much room"), but that call belongs to whoever designs E1's actual shape, not to this
  note.

**Conclusion:** E1 is **not** a fresh design, and it is **not** a mechanical copy-paste either — it
is a narrow, well-scoped adaptation: take `ContributionDescriptor`+`SizeHint`+the registry's
validation behaviour close to as they already exist in Elite's tree, and change exactly one thing
before they land here — `place`/`surface_id` go from Elite's closed `Place` `Enum`/global
`Surface` lookup to an opaque, app-supplied identifier, with `Surface` injection (already present
as a constructor parameter, just not yet mandatory) becoming the only way to configure the
registry rather than a default. That is a real design decision (how opaque, `str` vs. a typed
wrapper) worth designing deliberately rather than guessed here — surfaced for the user rather than
picked unilaterally, per `ONBOARDING.md` §9 and `code-rule.md` §9's own "no commit without being
asked" standing next to it: this is a shape decision, not a routine implementation choice.

**Decided and landed 2026-09-19, by user instruction, "design the opaque-identifier approach in
Elite since it owns the mechanism, then harvest to the engine."** The `str` vs. typed-wrapper
question above resolved to `str`: Elite's own `Place` became `class Place(str, Enum)` (was a bare
`Enum`) in its `src/core/contracts/place.py`, mixing in `str` rather than switching to `StrEnum` —
verified empirically on Elite's own Python 3.12 interpreter that the mixin changes nothing about
`__str__`/formatting (unlike `StrEnum`, which does) and only adds `isinstance(place, str)` /
`place == "some_string"`; matches Elite's own dominant ~40-file `(str, Enum)` precedent
(`TradingVenue` etc.) rather than the single `StrEnum` precedent. This satisfies `place: str` on
this engine's own `ContributionDescriptor` without Elite's `Place` `Enum` ever being imported here
— exactly the "opaque string the app registers" this file's own text above already required. Full
verification on Elite's side: `ruff`/`mypy` clean (632 files), `tests/unit/architecture` 420
passed, 106 targeted tests, full `tests/unit` (4883 passed) and `tests/integration` (161 passed, 4
skipped) both clean of `FAILED|ERROR|Traceback|ResourceWarning`. The engine-side harvest itself —
`ContributionDescriptor`/`SizeHint`/`SurfaceDeclaration`/`ContributionError`/
`IContributionRegistry`/`ContributionRegistry` — is recorded in the E1 table row above; **Elite's
own consumption of this engine mechanism (replacing its app-side `ContributionRegistry`/
`contribution_assembly.py` with these types) is not part of this landing** and stays a future
consumer-side migration, same as this task's own §"Note added 2026-09-19" already flagged for
`Surface`.

**E3 is separately blocked, not just unstarted**: Elite's `EPIC-025F` names this task
(`TASK-043`/`EPIC-001D`) as its own blocker, in both directions — a genuine chicken-and-egg the
harvest table already resolves correctly: E3 is triggered *by* the consumer's Phase 5 landing a
working `NavigationService`-shaped mechanism in its own tree first (the same harvest pattern as
E1/E2), which Phase 5 cannot yet do because it currently has nothing but its own legacy
`ScreenRegistry` to build from. Untangling that either needs the consumer to prototype
`NavigationService` app-side against `ScreenRegistry`'s current shape (mirroring what
`examples/student_management/docs/ui_extension_lifecycle.md` already did for objective 5's
ordering question, §"Two lifecycles" above) or a user decision to build E3 here first, ahead of a
live consumer, as a deliberate exception to the harvest rule.

**Decided 2026-09-19, by user instruction ("make the call").** Path (a): the consumer prototypes a
`NavigationService`-shaped mechanism in its own tree first, against its current `ScreenRegistry`,
the same harvest-first pattern every other step of this table already follows — not path (b),
building E3 here ahead of any live consumer. Reasoning: harvest-first won every prior step (E0/E1)
precisely because the engine did not have to guess a shape no real consumer had proven; breaking
that rule for E3 alone, with no other justification than "it is currently blocked," would repeat
the exact mistake this task's own header already warns against ("start there, not from a fresh
design"). This is a decision about *sequencing*, not a design of `NavigationService` itself — that
design still happens in the consumer's own tree, against its own `EPIC-025F`, verified there before
anything lands here. Consumer's `EPIC-025F` is updated with the matching decision in the same
session.

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
