# EPIC-002 — Audit Report

Consolidates every finding from `EPIC-002A` (backend) and `EPIC-002B` (UI), plus a fresh
re-check of `.agents/context/*.md` against what building `examples/student_management/`
actually required. Every claim below traces to a file/line/command — see
`.agents/rules/surprising-findings.md`'s standard, which this report is held to.

---

## 1. `.agents/context/*.md` — verified against the real build, not re-guessed

### 1.1 Already known wrong (from the epic's own README evidence table, re-confirmed still true)

| Claim | Reality |
| :--- | :--- |
| `repository.md` opening line: *"The `Sagittarius_ForkBoy` repository"* | Wrong repo name |
| `repository.md` lists `extensions/sqlalchemy` | Does not exist; real package is `persistence` |
| `repository.md` / `modules.md` omit `docs/` and `scripts/` | Both exist, substantial |
| `modules.md` documents `IModule` as the module model | Engine's own code calls it *"a legacy `IModule`"* |
| `interfaces/i_engine_context.py:30` docstring names `AppRunner` | No such class exists |

### 1.2 Newly found, verified 2026-08-23 while writing this report — `api.md`

`context/api.md`'s "Primary Kernel APIs" section, checked line-by-line against the real
interfaces used to build both `EPIC-002A` and `EPIC-002B`:

| Claim in `api.md` | Reality | Evidence |
| :--- | :--- | :--- |
| `app.boot(auto_discover=True)` | `auto_discover` is typed `str \| None`, not `bool`. `Bootstrap.boot()` passes it straight to `discover_and_load(auto_discover)`, which expects a package name string (`sdk/templates/clean/main.py`'s own working example: `auto_discover="modules"`). Passing `True` doesn't match any real usage in the codebase. | `kernel/bootstrap.py:17,31` |
| `IEngineContext` provides `container`, `event_bus`, `tasks` | Omits `logger` — a fourth port every real extension in this codebase resolves (`LoggerExtension`, `StudentManagementExtension`, `PySideMvcExtension` all do `container.resolve(ILogger)` indirectly via `BasePresenter`/direct calls). | `interfaces/i_engine_context.py`; this app's own `RosterPresenter.__init__` via `BasePresenter` |
| "Key Interfaces": lists `IModule`, `IHostedService`, `IEventBus`, `IContainer` | **Omits `IExtension` entirely** — the interface this app's `StudentManagementExtension` and `PySideMvcExtension` both implement, and the one every shipped extension in the engine (`LoggerExtension`, `DatabaseExtension`, `HealthExtension`, `AuditExtension`, `ThreadManagerExtension`) implements. `IModule` is presented as *the* module interface with no mention that the engine's own code calls it legacy. | `sagittarius_engine/extensions/*/`, this app's `infrastructure/persistence/extension.py` and `infrastructure/ui/pyside_mvc_extension.py` |
| `IModule`: "Must implement `register(app)` and `boot(app)`" | Omits `shutdown(app)`, a third required method. | `interfaces/i_module.py` |
| `IContainer`: lists `bind`, `singleton`, `resolve` | Omits `scoped()` and `create_scope()` — 2 of 5 real methods missing. | `interfaces/i_container.py` |

This is the same failure shape as `repository.md`/`modules.md`: not stale by omission of
something new, but wrong about the *shape* of an API this session used constantly, in a file
nobody had reason to open until an app was actually built against it.

## 2. Implicit assumptions the engine makes, written down nowhere before now

1. **`App(container, event_bus)` does not register either into the container.** Passing them
   to the constructor only makes them reachable via `app.event_bus`/`context.event_bus` — not
   via `container.resolve(IEventBus)`/`container.resolve(IConfig)`. Any extension or handler
   whose constructor asks for one by type fails at *dispatch* time, not boot time, unless the
   composition root explicitly does `container.singleton(IEventBus, event_bus)` /
   `container.singleton(IConfig, config)` first. (`docs/bootstrap.md`)
2. **Extension registration order is a real, unenforced dependency graph.** `app.use()` call
   order is the only thing establishing it — nothing in `IExtension`'s `dependencies`/
   `priority` fields is consulted automatically at registration time for a simple linear
   chain. Verified by deliberately reversing `DatabaseExtension`/`StudentManagementExtension`
   order and reading the real `DependencyResolutionError`. (`docs/module_registration.md`)
3. **A relative path in `config.json` resolves against the process's CWD, not the config
   file's own location.** Not an engine bug — ordinary `pathlib`/JSON behavior — but nothing
   in the engine's docs warns a new consumer about it, and it's the kind of mistake that fails
   silently (wrong file opened, or a new one silently created) rather than loudly.
   (`docs/config_loading.md`)
4. **`TransactionMiddleware` commits once per dispatched command; nothing else does.** A
   repository or script that touches `ISession` outside `app.dispatch()` must commit
   explicitly — there is no ambient auto-commit. (`docs/persistence_and_transactions.md`)
5. **`QApplication` must exist before `pyside_mvc` boots as an `IExtension`.** Resolved
   cleanly by constructing it before `App.boot()` in the composition root — but this ordering
   requirement is not stated anywhere the engine's own docs, and would not be obvious to a
   consumer wiring a GUI extension for the first time. (`docs/ui_extension_lifecycle.md`)
6. **`qInstallMessageHandler` does not see QML JS-engine `TypeError`s.** They print directly
   to stderr through a path Qt's message-handler system never touches. This codebase's own
   established "zero warnings" test technique (`test_gallery_emits_no_qml_runtime_warnings`)
   has a real blind spot here — worth knowing before trusting a clean `qInstallMessageHandler`
   capture as proof nothing happened. (`docs/ui_extension_lifecycle.md`, full account there)

## 3. Real engine gap, filed — not worked around invisibly

**[`TASK-019`](../../backlog/TASK-019_database_extension_expose_engine.md)** —
`DatabaseExtension` builds a SQLAlchemy `Engine` internally to satisfy `ISession`, but never
exposes it anywhere a consumer can reach it (not in the container, not as a property on
`ISession`/`SQLAlchemySessionAdapter`). Confirmed by reading both files in full and grepping
for `Engine` registrations in `extensions/persistence/` (zero hits). Consequence: no
sanctioned way for a consuming app to run `Base.metadata.create_all()` or any other
engine-level operation. Workaround (`StudentManagementExtension`, see
`docs/persistence_and_transactions.md`) rebuilds a second `Engine` from the same config value
— correct only for a file-based URL, guarded against `:memory:` with an explicit `ValueError`.

## 4. A retracted finding, kept here for the record

A task was filed against `QmlHostView`'s constructor (reparenting its `QQuickWidget` before
`setSource()`) after what looked like a reproducible QML runtime-warning defect. **It was
wrong, and retracted the same day.** The real cause of the confusion: piping test output
through `tail -N` had been hiding pytest's own `N passed` verdict underneath a flood of raw
QML stderr noise, across many re-runs — the tests had been passing the whole time. Clean,
untruncated exit-code checks proved the reparent order made no difference at all (byte-
identical stderr either way). Full account, including how it was caught, in
`docs/ui_extension_lifecycle.md`'s last section. Recorded here per
`.agents/rules/surprising-findings.md`'s "I was wrong is reportable on the same terms" —
and as a standing warning: **do not trust a `tail`-truncated verdict from this codebase's test
output; always check the real exit code or the untruncated summary line.**

## 5. Module coverage — honest, not forced (full detail in `MODULE_COVERAGE.md`)

Every top-level package and extension in `sagittarius_engine/` resolved to exactly one of
Used/Skipped/Gap, with a domain-specific reason for every Skip — not restated in full here
(see the ledger itself), but the shape of the reasoning is worth naming: this app skipped
`adapters/` (a different, equally valid CLI-input pattern already existed, better suited to
7 differently-shaped subcommands than a single-command-key REPL loop), `cqrs` (skipping it is
*compliance* with `architecture.md`'s own Layer 2 rule against importing it into the
Application layer, not an oversight), and `audit`/`fsm`/`health`/`thread_manager`/`sdk`
(no genuine need in a synchronous CRUD roster app — forcing any of them in would have
fabricated an integration pattern nobody asked for, exactly what this epic's own `ONBOARDING.md`
§3 point 3 warns against).

## 6. Where "the reasonable thing" and "what the engine required" diverged

- **Reasonable:** a `Student` domain event decorated with `@dataclass` needs nothing special
  to also inherit `BaseEvent`'s `event_id`/`occurred_on`. **Required:** `BaseEvent` is not
  itself a dataclass, so its `__init__` is never called automatically — a subclass must
  explicitly call `BaseEvent.__init__(self)` from `__post_init__`, or construction succeeds
  silently and `event_id` raises `AttributeError` only when later accessed. Documented inline
  in `domain/events.py` for the next contributor adding a 4th event.
- **Reasonable:** `AppDataTable`'s widget-kit precedent (used extensively, cleanly, in
  `Gallery.qml`) suggested it would work identically once dropped into any screen.
  **Required (and ultimately not actually a problem):** through a real `Presenter`'s
  synchronous `refresh()`, the exact same component produces a large flood of console noise
  no existing test technique catches — cosmetic only, self-healing, but a real surprise for
  anyone trusting `Gallery.qml`'s clean precedent as proof the component "just works"
  everywhere. See §2.6 and the retraction in §4 for the full story of how long this took to
  correctly diagnose.
- **Reasonable:** the CLI (`main.py`) and GUI (`gui.py`) could share `build_app()` outright.
  **Required:** a small `extra_extensions` parameter, since the GUI needs `PySideMvcExtension`
  registered and the CLI must not (no `QApplication` exists in a headless CLI run).
