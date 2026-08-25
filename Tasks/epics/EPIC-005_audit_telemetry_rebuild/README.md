# EPIC-005: Audit Telemetry — Teardown and Rebuild

- **Status**: 📋 **Spec awaiting approval — nothing deleted, nothing implemented yet**
- **Created**: 2026-08-25
- **Priority**: P2
- **Category**: Observability / Diagnostics
- **Supersedes**: `TASK-002` (`AuditExtension` & CLI Inspector, marked ✅ Completed 2026-07-28 — see §2)
- **Related**: `TASK-033` (renamed `audit_dashboard.py` → `audit_dashboard_cli.py`)

---

## 1. What this feature is actually for

A **remote observability console for a live engine process**.

Sagittarius hosts long-running things that have no UI of their own — background workers,
trading bots, automation pipelines, plugin hosts. When one of those is running, there is no
way to see inside it without attaching a debugger or reading log files after the fact.

The audit feature is meant to answer, *while the process is running*:

- Which extensions are loaded, and are they enabled?
- Which `IHostedService` instances actually started?
- What background tasks exist right now — status, progress, runtime, and the error if one failed?
- What scheduler jobs are registered and when do they next run?
- Is the app healthy (`HealthCheckQuery`)?
- What does the middleware pipeline look like, what config keys are loaded, how many handlers
  are on each event?
- What happened recently (rolling event log), and how long has the process been up?
- What is it costing (CPU / RSS)?

The shape is deliberately **two processes**:

```
engine process                          operator's machine
┌──────────────────────────┐            ┌─────────────────────┐
│ App + AuditExtension     │            │  audit client       │
│   AuditService (collect) │──ws://─────▶│  (renders it live)  │
│   Broadcaster (publish)  │  telemetry │                     │
└──────────────────────────┘            └─────────────────────┘
```

Separating them is the right call and is **not** what this epic changes: the console must not
die with the app it observes, must be attachable to an already-running process, and must add
no UI dependency to the engine. The engine side stays a normal `IExtension` so an app opts in
with one line and pays nothing when it is off.

**This epic does not question the goal. It replaces the implementation, which does not work.**

---

## 2. Verified current state

Every row below was reproduced on this branch (Python 3.14.0rc2, this repo's `.venv`), not
inferred by reading.

| # | Defect | Evidence |
| :-- | :--- | :--- |
| D1 | **The CLI client can never connect.** `audit_dashboard_cli.py` polls `http://localhost:9999/` with `urllib.request`. The engine only ever opens a **WebSocket** server on that port — there is no HTTP server anywhere in `sagittarius_engine/` (`grep` for `HTTPServer`/`http.server`/`socketserver` returns nothing). It renders `🔴 Connection Error` on every refresh, forever. | Started the real `WebsocketBroadcaster`, called the CLI's own `fetch_telemetry()` against it → returned `None`. |
| D2 | **The GUI client renders a raw Python dict.** `MainWindow.on_telemetry_received()` is `self.log_area.append(str(data))` — the whole payload `str()`-dumped into a read-only `QTextEdit`. No tables, no task list, no health panel. | `tools/audit_dashboard/presentation/main_window.py:53` |
| D3 | **The client's entire Domain layer is dead code.** `EngineTelemetry`, `SystemHealth`, `EnvironmentMetrics`, `TaskDetail`, `ExtensionInfo` are defined and re-exported — and constructed *nowhere*. There is no mapper from wire payload to entity. | `grep` for each name outside `Domain/`: only hits are `Domain/__init__.py` re-exports. |
| D4 | **Server and client schemas do not match, so D3 could not be fixed by just calling the constructor.** Server sends `uptime`, `tasks`, `extensions`, `environment{os, os_release, python_version, cpu_percent, ram_mb}`. Client entity expects `uptime_seconds`, `active_tasks`, `loaded_extensions`, `environment{hostname, os_name, python_version, memory_usage_mb: float, cpu_cores: int}`. Different names, different types (`cpu_percent` is a formatted `str` like `"12.3%"`, not a number), fields on each side the other never produces. | `audit_service.py:49-61` vs `Domain/entities.py` |
| D5 | **The client imports a package that does not exist.** `from src.base_event import BaseEvent` and `from src.interfaces import ICommand, IEventBus` — there is no `src/` in this repo (the package is `sagittarius_engine/`). Both are wrapped in `try/except ImportError` that silently substitutes empty stub classes, so the "use case" and "event" layers are decorative: `ICommand.execute` is `pass`, `IEventBus.emit` is `pass`. | `event/dashboard_events.py:4`, `application/receive_audit_use_case.py:8`; `ls src` → not found |
| D6 | **The `sagittarius-audit` console script is broken two ways.** (a) Inner imports are bare (`from application...`, `from Domain.ports...`), which only resolve if cwd is `tools/audit_dashboard/` — hence `ModuleNotFoundError: No module named 'application'`. (b) The entry point `tools.audit_dashboard:main` binds `main` to the **module**, not the function, so the generated script's `sys.exit(main())` would raise `TypeError: 'module' object is not callable` even after (a) is fixed. | Ran `.venv/bin/sagittarius-audit`; inspected the generated script and `pyproject.toml:31` |
| D7 | **The GUI never ships to users.** `tools/audit_dashboard/` has no `__init__.py`, so `find_packages(include=["sagittarius_engine*","tools*"])` returns `['tools']` only. A `pip install` of this project gets the `sagittarius-audit` command but not the package it points at. | `find_packages(...)` → `['tools']`; `audit_dashboard in wheel? False` |
| D8 | **The engine extension knows about demo-app events.** `AuditService._subscribe_events()` hard-codes `student.added`, `student.updated`, `student.deleted`, `report.completed` — `examples/student_management` domain events, subscribed from inside the framework. A layering inversion, and useless for any other app. | `audit_service.py:96-100` |
| D9 | **Every subscribed event triggers a full state re-collection and broadcast.** `on_state_changed` calls `_get_full_state()` — which dispatches a health query, walks all tasks, extensions, services, scheduler jobs, config and event-bus internals — then serialises and sends the lot. A task-heavy workload makes the observer a load source on the thing it observes. No coalescing, no rate limit, no delta. | `audit_service.py:69-79` |
| D10 | **Zero client tests.** All 13 audit tests (`test_audit_extension`, `test_audit_integration`, `test_websocket_broadcaster_auth`) cover the engine side. Nothing tests any client, which is how D1–D6 survived. | `pytest -k audit --collect-only` → 13 tests, all under `tests/extensions/` |

Smaller items, same cleanup: `AuditService` reaches into privates (`eb._handlers`, `config._config`); `get_full_config()` guesses at four different attribute names and returns `{"error": ...}` as if it were data; `AuditExtension` docstrings still say *"Telemetry **HTTP** Server"*, left over from before the WebSocket refactor; `auth_token` defaults to `None` (no auth); `run_dashboard.ps1` is Windows-only with no shell equivalent.

**Assessment.** The engine half is real, tested, and mostly sound — the collection logic in
`AuditService` is the genuinely valuable part and its *content* is worth keeping even though
this epic reimplements its plumbing. The client half is a scaffold: correct-looking Clean
Architecture folders (`Domain/`, `application/`, `event/`, `infra/`, `presentation/`) wired to
nothing, with the one line that matters printing a `dict`. **Both clients are 100%
non-functional today** — D1 means the CLI never shows data, D2/D7 mean the GUI shows a dict
dump and is not installable. `TASK-002`, which declared this ✅ Completed on 2026-07-28, was
not verified end-to-end.

---

## 3. Scope of the teardown

Approved direction: **delete all of it, server included, and redesign the protocol from
scratch.** Recorded here for approval before anything is removed.

**To delete**

| Path | Notes |
| :--- | :--- |
| `tools/audit_dashboard/` | GUI client, 13 files |
| `tools/audit_dashboard_cli.py` | TUI client (D1 — never worked) |
| `sagittarius_engine/extensions/audit/` | Engine extension: `audit_extension.py`, `audit_service.py`, `ports.py`, `infra/websocket_broadcaster.py` |
| `tests/extensions/test_audit_extension.py`<br>`tests/extensions/test_audit_integration.py`<br>`tests/extensions/test_websocket_broadcaster_auth.py` | 13 currently-passing tests |
| `[project.scripts] sagittarius-audit` in `pyproject.toml` | Re-added in Milestone C pointing at the new entry point |

**Cost of deleting the server too.** 13 green tests go away, and `WebsocketBroadcaster` —
which is the one piece that genuinely works, including the token auth added by `TASK-017` and
the ephemeral-port/`_ready_event` handling that makes it testable — gets rewritten. Milestone A
must not lose those behaviours: the auth test and the bind-readiness test come back as tests
against the new broadcaster. The collection logic in `AuditService` should be re-read as the
spec for *what* to collect even though the class itself is replaced.

**Not touched:** `HealthExtension` (the audit feature depends on it, it is independently
useful), and `examples/student_management` (D8 only ever coupled in the other direction).

**Before deleting:** tag the current tree (`git tag pre-epic-005-audit`) so the old
implementation stays trivially recoverable without archaeology.

---

## 4. Target design

### 4.1 One contract, imported by both sides

D3/D4 exist because two hand-maintained schemas drifted. The fix is that **there is only one**,
in the engine package, imported by the client:

```
sagittarius_engine/extensions/audit/contracts.py
```

Frozen dataclasses (`EngineTelemetry`, `SystemHealth`, `TaskDetail`, …) with explicit
`to_dict()` / `from_dict()`, plus `PROTOCOL_VERSION`. Stdlib only — no pydantic; the engine's
domain rule is stdlib-only and `pydantic` is currently broken on 3.14rc2 anyway.

The client imports these. It does not redeclare them. A field rename is then a compile-time
problem in one file instead of a silent runtime mismatch. Types are real types — `cpu_percent:
float`, not `"12.3%"`; formatting is the renderer's job (D4).

### 4.2 Wire protocol v1

Every frame is one JSON object:

```jsonc
{
  "v": 1,                        // PROTOCOL_VERSION — client refuses a major mismatch, loudly
  "type": "snapshot",            // "snapshot" | "delta" | "event" | "error"
  "seq": 42,                     // monotonic; client detects gaps
  "ts": "2026-08-25T10:30:00Z",  // UTC ISO-8601
  "data": { }                    // EngineTelemetry.to_dict() for "snapshot"
}
```

- `snapshot` — full state. Sent once on connect, then as a keepalive every `snapshot_interval`
  (default 10s).
- `delta` — only what changed since `seq-1`. The normal steady-state frame.
- `event` — one entry for the rolling event log, sent as it happens.
- `error` — server-side collection failure, surfaced to the operator instead of swallowed into
  a log line (contrast: today's `except Exception: self._logger.error(...)` in eleven places,
  where the client just sees a field quietly go missing).

The version handshake is the direct fix for D1: a transport/schema mismatch must fail *visibly
at connect*, not degrade into a blank panel.

### 4.3 Engine side

- `AuditExtension` — unchanged in spirit: `register()` binds the service, `boot()` starts the
  broadcaster when enabled, `shutdown()` stops it. Docstrings fixed (D-misc: no more "HTTP").
- `TelemetryCollector` — pure, synchronous, no I/O. `collect() -> EngineTelemetry`. Being pure
  is what makes it unit-testable against a fake context, which is what `AuditService` is not
  today.
- `ITelemetryBroadcaster` + `WebsocketBroadcaster` — port kept (it is a good port), rebuilt with
  the auth and readiness behaviour ported over from the current implementation.
- **Subscription is configuration, not code** (D8):
  `AuditExtension(events=["task.*", "student.added"])` — the app names its own events; the
  framework hard-codes none.
- **Publishing is throttled** (D9): a collector thread at `min_interval` (default 500ms)
  coalesces bursts; N events inside one window produce one frame. `event` frames stay
  immediate — they are small — but state re-collection is rate-limited.
- Reaching into privates (`eb._handlers`, `config._config`) is replaced by a narrow read-only
  accessor on each subsystem, or that field is dropped. An observability tool must not be the
  reason a private stays frozen.

### 4.4 Client side

Layering as it should have been (D5 — no `try/except ImportError` stubs anywhere; the client
depends on the engine package outright, and if the import fails it fails at startup with a
real message):

```
transport  →  decode + version check  →  EngineTelemetry  →  renderer
```

Renderer is the only layer that differs per UI form, and it is the one decision left open
(§7). Packaging fixes D6/D7: a real `__init__.py`, absolute imports, and the entry point
pointing at `...main:main` — verified by actually building a wheel and running the command
from a clean venv, which is the check `TASK-002` skipped.

---

## 5. Milestones

| ID | Scope | Done when |
| :-- | :--- | :--- |
| **EPIC-005A** | Teardown + `contracts.py` + protocol v1 + `TelemetryCollector` + rebuilt broadcaster | Old tree tagged and deleted; collector unit-tested against a fake context; auth + readiness tests restored and green; a raw `websockets` client receives a schema-valid `snapshot` |
| **EPIC-005B** | Client: transport, decode, version handshake, mapping to `EngineTelemetry` | Round-trip test: real engine → real client object graph, asserted field by field. The test that would have caught D1 and D4 |
| **EPIC-005C** | Renderer (form per §7) + packaging + docs | `pip install dist/*.whl` in a clean venv, `sagittarius-audit` connects to a running demo app and renders live. `.agents/context/` updated; `TASK-002` marked superseded |

Order matters: **B before C.** D1–D4 are all "the pipe was never tested end to end"; the
round-trip test has to exist before any pixels are drawn.

---

## 6. Acceptance criteria

1. `sagittarius-audit`, installed from a built wheel into a clean venv, connects to a running
   engine and renders live telemetry. *(D1, D6, D7)*
2. Health, extensions, hosted services, tasks (with progress and error), scheduler jobs, config
   keys, event-bus handler counts, middleware pipeline, uptime, CPU/RSS and the rolling event
   log are all rendered as **structured output** — no `str(dict)` anywhere. *(D2)*
3. A round-trip test asserts a real engine's frame decodes into the expected `EngineTelemetry`.
   Renaming a contract field breaks it. *(D3, D4)*
4. No `try/except ImportError` fallback stubs, and no import of any package outside this repo.
   *(D5)*
5. No framework module names an application-specific event. *(D8)*
6. With 1000 task events in 10 seconds, frames sent stay bounded by the throttle, and a
   benchmark shows collection overhead with the dashboard **off** is nil. *(D9)*
7. Client and protocol have their own tests; `pytest -k audit` covers both sides. *(D10)*
8. Auth: connecting without a token when one is configured is rejected — test restored from
   `test_websocket_broadcaster_auth.py`. Binding to anything other than loopback without a
   token is refused at startup.
9. A version-mismatched client fails at connect with a clear message, not a blank panel.

---

## 7. Open decisions — need your call before EPIC-005C

1. **Client form.** *(the question left unanswered)*
   - **TUI (`rich`)** — recommended. Runs over SSH on a headless box, which is where the
     processes worth observing actually live. No Qt, no display. `rich` is already the
     `[audit]` extra. Testable by asserting on rendered text.
     A GUI that cannot attach to a server is the wrong tool for the job this feature exists to do.
   - **GUI (PySide6)** — nicer charts, but needs Qt + a display, is heavy to test, and is the
     form that just failed.
   - **Both over one core** — the `transport → decode → contracts` split makes this cheap
     later; not worth doing in the first pass.
2. **Auth default.** Require a token always (safe, one more setup step), or keep
   loopback-without-token as today's convenience? Recommendation: token required whenever the
   bind address is not `127.0.0.1`, which is criterion 8.
3. **Client location.** `tools/audit_dashboard/` (a dev tool, stays out of the wheel) or
   `sagittarius_engine/extensions/audit/client/` (ships with the package, so `pip install` is
   enough)? Recommendation: the latter — criterion 1 is otherwise unmeetable without a separate
   distribution.
4. **`psutil`.** Currently an optional import degrading to `"N/A"`. Make it a declared extra
   (`[audit]`) and report absence explicitly, or drop CPU/RSS from v1?

---

## 8. Risks

- **13 green tests are deleted before their replacements exist.** Mitigated by the tag, and by
  A restoring auth + readiness coverage before B starts. This is the real cost of tearing down
  the server as well as the clients.
- **Protocol v1 designed against exactly one client** may bake in assumptions. Cheap insurance:
  keep `data` a plain dict at the transport boundary so a non-Python consumer stays possible.
- **Scope creep into engine internals.** §4.3's "narrow read-only accessor" touches event bus,
  config, and scheduler. If any turns out to be more than a property, it becomes its own task
  rather than growing this epic.
