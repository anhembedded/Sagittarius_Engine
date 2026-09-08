# Examples

Rewritten 2026-08-23 — the previous version described the old `examples/student_management/`
(deleted, `IModule`-based, CQRS, never touched `pyside_mvc`). This describes its real
replacement, built by `EPIC-002` specifically to be a permanent, accurate reference — treat it
as the first thing to point at for "how do I actually use this engine," ahead of this file.

## Student Management (`examples/student_management/`)

A real, running Clean Architecture app with a QML UI, backend and frontend both.

### Backend

- **Domain** (`domain/`): `Student`, `Email`, `StudentId` — pure Python, no engine imports.
  `events.py`: `StudentEnrolled`/`StudentUpdated`/`StudentRemoved`, subclassing the engine's
  own `domain.base_event.BaseEvent`.
- **Application** (`application/`): 7 use cases as directories (`command.py` + `handler.py`) —
  `enroll_student`, `update_student`, `remove_student`, `get_student`, `list_students`,
  `search_students`, `generate_roster_report`. Ports in `application/ports/`
  (`IStudentRepository`).
- **Infrastructure** (`infrastructure/`): `SqlAlchemyStudentRepository` — real SQLite
  persistence via the engine's `persistence` extension (`ISession`). `StudentManagementExtension`
  — a real `IExtension`, declares `dependencies = ["DatabaseExtension"]` (see `modules.md`).
- **`main.py`**: `argparse` CLI — `enroll`/`update`/`remove`/`get`/`list`/`search`/`report`.

### UI

- **`gui.py`**: real entry point. Constructs `QApplication` *before* `App.boot()` —
  load-bearing order for booting `pyside_mvc` as an `IExtension`, see `ui-architecture.md` and
  the sample's own `docs/ui_extension_lifecycle.md`.
- **`presentation/`** splits by abstraction level, not just by name (2026-08-23 — the two used
  to sit flat in one directory): `presentation/roster/` is the roster screen's own MVP triad —
  `RosterView` (`QmlHostView`), `RosterPresenter` (`BasePresenter`, no FSM — a roster screen has
  no lifecycle states), `RosterViewModel` (`BaseQmlViewModel`) — while `presentation/theme/`
  holds app-wide UI configuration consumed only by `infrastructure/ui/pyside_mvc_extension.py`
  (`PySideMvcExtension`, the app-side `IExtension` wrapper booting `pyside_mvc` — no such class
  ships in the engine yet), never by the screen itself: `palette.py`'s colour tokens and
  `icon_loader.py`'s `SimpleIconLoader`.
- **`presentation/roster/qml/RosterScreen.qml`**: composes `AppDataTable` (roster rows),
  `BaseCard` (stats summary, with a real compact-mode toggle bound to the ViewModel), `AppModal`
  (enroll form) — the widget kit used for real, not for coverage.

### Patterns demonstrated

- **`IExtension`, not `IModule`** — see `modules.md`.
- **Declarative extension dependencies** — `dependencies = [...]`, not `app.use()` call order.
- **Event-driven UI refresh** — `RosterPresenter` never manually refreshes after a dispatch;
  it subscribes to the same domain events the CLI would also see, and refreshes in response.
- **`pyside_mvc` booted as a real `IExtension`** — the first sample app in this repo that
  doesn't skip `pyside_mvc` for plain `QtWidgets`.

### Runtime state console (`EPIC-007`)

A fourth entry point, `console.py`, boots the app headlessly with `StateConsoleExtension`
attached instead of the GUI or CLI — see [`state_console.md`](state_console.md). Its
`--demo-faults` flag additionally attaches `DemoFaultsExtension`
(`infrastructure/demo_faults/`), which seeds one instance of every condition the engine's
diagnostics claim to catch (a typo'd subscription, a dead-lettered event, an unbound
dependency, a dead scheduled job, a held exclusive slot, a rejected state-machine transition)
— opt-in, and never in `doctor_target.build()`'s own path, so it cannot regress the CI wiring
gate. Full seed table and reasoning:
[`docs/runtime_state_console_demo.md`](../../examples/student_management/docs/runtime_state_console_demo.md).

### Honest module coverage

Not every engine module is used — forcing one in without a genuine need would teach a
fabricated pattern. See
[`MODULE_COVERAGE.md`](../../Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/MODULE_COVERAGE.md)
for every package/extension, resolved to Used/Skipped/Gap with a reason for each.

### Design docs (`docs/`)

Five, each with a Mermaid diagram, written as their topic was settled while building:
`bootstrap.md`, `module_registration.md`, `config_loading.md`,
`persistence_and_transactions.md`, `ui_extension_lifecycle.md`. Read these for the "why," not
just the "what" — each documents a real decision or a real trap hit while building this app,
with evidence, not a guess.

### How to run

```bash
# CLI
python -m examples.student_management.main enroll "Alice Nguyen" alice@example.com CS 3.7
python -m examples.student_management.main list

# GUI
python -m examples.student_management.gui

# headless, with the runtime state console attached
python examples/student_management/console.py --demo-faults
```

Or, from PowerShell, `run.ps1` picks the mode: `-Cli`, `-Console [-DemoFaults]`, or the GUI by
default (`examples/student_management/run.ps1`'s own comment-based help has every switch).

### Tests

`pytest examples/student_management/` — 64 tests, also collected automatically by the root
suite (no special config needed; `pyproject.toml` sets no `testpaths` restriction).
