# Module Coverage Ledger

**Owner subtasks:** [EPIC-002A](completed/EPIC-002A_sample_app_scaffold.md) for every row
except `pyside_mvc`, which was [EPIC-002B](completed/EPIC-002B_pyside_mvc_integration.md)'s
own deliverable — both now resolved, every row filled in, no "TBD" remaining.

Why this file exists: prose claims of "honest module coverage" aren't verifiable — see
`ONBOARDING.md` §3's "not a promise, it's checked against a ledger." Every top-level
`sagittarius_engine/` package and every shipped extension gets exactly one row, resolved to
one of three states:

- **Used** — cite the file/line in `examples/student_management/` that proves it.
- **Skipped** — the domain-specific reason it has no genuine use here.
- **Gap** — the module doesn't do what the sample needs; cite the filed `TASK-XXX`
  (per `ONBOARDING.md` §6, a gap gets a task immediately, not just a description here).

This list is exhaustive — generated from `ls sagittarius_engine/` and
`ls sagittarius_engine/extensions/` on 2026-08-23. If a new top-level package or extension is
added to the engine after this table is filled in, add a row; don't let the table go stale
the way `.agents/context/` did.

## Top-level packages

| Package | Status | Evidence / Reason |
| :--- | :--- | :--- |
| `adapters/` | Skipped | `adapters/cli`'s `CLIInputPort`/`CLIOutputPort` pair with `ApplicationRunner`'s single-command-key REPL loop (`kernel/app_runner.py`, read in full 2026-08-23). This app's 7 subcommands each take distinct typed arguments (`enroll` needs 4 positional args, `update` needs optional flags) — `argparse` subparsers (`main.py`) fit that shape better. A considered alternative, not an oversight. |
| `base/` | Skipped | `BaseModule` is for the legacy `IModule` path, rejected — see `docs/module_registration.md`. `BaseInputPort`/`BaseOutputPort` only matter if `adapters/cli` were used (also skipped, above). |
| `domain/` | Used | `domain/events.py` — `StudentEnrolled`/`StudentUpdated`/`StudentRemoved` all subclass `sagittarius_engine.domain.base_event.BaseEvent`. |
| `exceptions.py` | Skipped | No engine-specific exception type is caught or raised by this app's own code. The container's `DependencyResolutionError` was only *observed* during verification (`docs/module_registration.md`), never referenced in application code. |
| `infrastructure/` | Used | `main.py:build_app()` — `StdLibContainer`, `MemoryEventBus`, `ConfigManager` + `JsonSource` (via `load_json`) + `EnvSource` (via `load_env`); `StdLogger` registered transitively via `LoggerExtension`. |
| `interfaces/` | Used | `IContainer`, `IEventBus`, `IConfig`, `ILogger`, `IExtension`, `ISession` — throughout `application/` and `infrastructure/`. |
| `kernel/` | Used | `App` — construction, `use()`, `use_middleware()`, `boot()`, `dispatch()`, `stop()` all exercised in `main.py` and `tests/test_app_integration.py`. |
| `middleware/` | Used | `LoggingMiddleware` — `main.py:build_app()`. |
| `runtime/` | Skipped | No `IHostedService`, `Scheduler`, or `AsyncRuntime` API called directly by this app. (Every `App` instance starts/stops an `AsyncRuntime` loop and `Scheduler` automatically as part of its own lifecycle — observed in boot/stop logs — but that's the engine using its own package, not this app choosing to.) A synchronous CRUD CLI has no background/scheduled work to hand it. |
| `sdk/` | Skipped | Dev-time project scaffolding, not a runtime dependency. This app was hand-built per the epic's explicit instruction, not `sdk`-generated. |
| `utils/` | Skipped | `NullLogger` unneeded (a real `StdLogger` is registered via `LoggerExtension`); `PathUtils` unneeded (`main.py`'s path handling is one `pathlib.Path` expression, too trivial to warrant the engine's utility wrapper). |

## Extensions (`sagittarius_engine/extensions/`)

| Extension | Status | Evidence / Reason |
| :--- | :--- | :--- |
| `audit` | Skipped | No audit-trail requirement for a student roster CRUD app — forcing one in would fabricate an integration pattern nobody asked for, exactly what `ONBOARDING.md` §3 point 3 warns against. |
| `cqrs` | Skipped, deliberately | Read `extensions/cqrs/interfaces/{commands,queries}.py` in full 2026-08-23: `ICommand`/`IQuery` are thin `Generic[TInput, TOutput] + IDispatchable` wrappers, mainly valuable for `app.dispatch()`'s mypy return-type inference. **Not used, on purpose** — `architecture.md`'s own Layer 2 guidance says *"Never import engine-specific interfaces (like `sagittarius_engine.extensions.cqrs.ICommand`) into the Application layer. Use the layer's own pure Python `ICommandHandler` interface."* This app's handlers use a plain `execute(dto)` shape instead — structurally compatible with `IDispatchable`/`app.dispatch()` without the coupling. Skipping this extension is *compliance* with this repo's own rule, not an oversight. |
| `fsm` | Skipped | No state-machine-shaped behavior anywhere in this domain (a student roster has no lifecycle states to transition between). |
| `health` | Skipped | Health checks fit a long-running server/daemon process; this is a one-shot CLI invocation that exits after each command. |
| `logger` | Used | `LoggerExtension` — `main.py:build_app()`. |
| `persistence` | Used | `DatabaseExtension` — `main.py:build_app()`, real SQLite via `ISession`/`SqlAlchemyStudentRepository`. **One real engine gap found and filed**, not silently worked around: [`TASK-019`](../../backlog/TASK-019_database_extension_expose_engine.md) (`DatabaseExtension` exposes no way to reach the raw `Engine` for schema creation) — see `docs/persistence_and_transactions.md` for the workaround applied here. |
| `pyside_mvc` | Used | `presentation/roster_view.py` (`QmlHostView`), `roster_presenter.py` (`BasePresenter`), `roster_view_model.py` (`BaseQmlViewModel`), `qml/RosterScreen.qml` (`AppDataTable`, `BaseCard` with a real compact-mode toggle, `AppModal`), `infrastructure/ui/pyside_mvc_extension.py` (real `IExtension`, calls `configure_app_qml()`). All 4 static guards (literal-colour, raw-primitive, rectangle-as-card, import-boundary) return zero findings against this code. Two prior sample apps in this repo (`student_management`, `tools/audit_dashboard`) both skipped `pyside_mvc` in favor of plain `QtWidgets` — this is the first one that doesn't. |
| `thread_manager` | Skipped | No concurrent or background work to manage — a synchronous CRUD CLI has nothing to hand to a thread pool. |
