# Testing Guide

Rewritten 2026-08-23 — the previous version's test-directory layout was fictional
(`tests/sanity/`, `tests/unit/`, `tests/integration/` — none exist). This one is generated
from the real tree, not recalled. See `rules/testing.md` for *when/how* to add tests — this
file is about *where things are and how to run them*, not duplicated there.

## Framework & coverage

- **Framework**: `pytest` (`pytest-asyncio` for async tests, `pytest-qt` for `qtbot`-based Qt
  widget tests).
- **Run everything**: `pytest tests/ --cov=sagittarius_engine --cov-report=term-missing`
- **Coverage gate**: 80% minimum, enforced in CI (`--cov-fail-under=80`).

## Real layout — exhaustive, not illustrative

`tests/` mirrors `sagittarius_engine/`'s own package layout:

```
tests/
├── base/            tests for base/
├── domain/          tests for domain/
├── extensions/      tests for extensions/ (audit, cqrs, fsm, health, logger,
│                    persistence, pyside_mvc, thread_manager — one subdir each)
├── infrastructure/  tests for infrastructure/
├── interfaces/      contract-level tests for interfaces/
├── kernel/          tests for kernel/ (App, Bootstrap, ExtensionManager, Dispatcher, ...)
├── middleware/      tests for middleware/
├── runtime/         tests for runtime/ (async_runtime, hosted, scheduler, tasks)
└── test_architecture.py   Enforces Clean Architecture boundaries — e.g., domain/ must not
                            import infrastructure/. Run in CI as its own "architecture" job.
```

`examples/student_management/tests/` follows the same mirroring principle at the app level —
`domain/`, `application/`, `infrastructure/`, `presentation/`, plus one top-level
`test_app_integration.py` wiring the real `App`. **Not a separate suite**: no `testpaths`
restriction is set in `pyproject.toml`, so `pytest` (run from the repo root, with no path
argument) collects `examples/`'s tests automatically alongside the engine's own.

## `pyside_mvc` / Qt-specific testing

- Use `pytest-qt`'s `qtbot` fixture, not manual `QApplication`/`processEvents()` loops — see
  `docs/ui_extension_lifecycle.md` (in the sample app) for a real, verified account of why:
  manual `processEvents()` calls are not sufficient to reliably realize a window before
  evaluating QML bindings; `qtbot.wait()` (or a real `app.exec()` in production) is.
- Set `QT_QPA_PLATFORM=offscreen` for headless test runs — but be aware
  `qInstallMessageHandler` does **not** catch QML JS-engine runtime errors (they print
  directly to stderr) — only `qWarning()`/`qCritical()`-routed messages. A clean
  `qInstallMessageHandler` capture is not proof nothing went wrong; see
  `docs/ui_extension_lifecycle.md`'s full account of a real, retracted false-positive this
  gap caused.
- **A documented, real trap when piping test output**: `tail -N`ing test output can hide
  pytest's own `N passed`/`N failed` summary line underneath a flood of raw stderr (QML
  runtime noise, in particular). Check the real exit code or the untruncated summary before
  trusting a "failure" read from truncated output.

## Mypy & lint (part of the same CI gate, not a separate step)

```bash
mypy sagittarius_engine tests --ignore-missing-imports --follow-imports=skip
ruff check sagittarius_engine tests
ruff format sagittarius_engine tests
```
