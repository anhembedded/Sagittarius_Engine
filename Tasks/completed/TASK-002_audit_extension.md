# TASK-002: `AuditExtension` Framework Observability & Diagnostics Dashboard

- **Status**: ⛔ **Superseded 2026-08-26** by
  [`EPIC-005`](../epics/EPIC-005_audit_telemetry_rebuild/README.md) — see §Superseded below.
  Was marked ✅ Completed 2026-07-28.
- **Completion Date**: 2026-07-28 *(the claim this note corrects)*
- **Priority**: P1 - High
- **Category**: Observability / Diagnostics

---

## ⛔ Superseded

**This task was marked ✅ Completed on 2026-07-28 while both of its clients were 100%
non-functional**, and that went unnoticed for a month. `EPIC-005` §2 reproduced ten distinct
defects on a branch rather than inferring them by reading — among them: the CLI client polled
`http://localhost:9999/` while the engine only ever opened a **WebSocket** there, so it rendered
a connection error on every refresh forever (`D1`); the GUI client's one line that mattered was
`str()`-dumping a dict into a read-only text box (`D2`); and the `sagittarius-audit` console
script could not start for any consumer in three independent ways (`D6`, `D7`).

The description below is left **unedited** as the record of what was intended and claimed. What
actually shipped is described in `EPIC-005` §2. Nothing in this file describes code that should
be built on:

| This task's plan | What supersedes it |
| :--- | :--- |
| `AuditService` snapshot collection over HTTP | `TraceRecorder` — a bounded ring buffer of timestamped records (`EPIC-005A`) |
| `AuditTerminalDashboard` TUI client | `sagittarius-trace attach` (`EPIC-005D`) — text stream, no widget |
| a bespoke dashboard UI | Perfetto and OpenTelemetry exporters (`EPIC-005C`) |
| `datetime.now().strftime("%H:%M:%S")` timestamps | `time.perf_counter_ns()`, monotonic, ns since a session epoch |

The engine-side modules this task produced (`extensions/audit/audit_extension.py`,
`audit_service.py`, `ports.py`, `infra/websocket_broadcaster.py`) and the `tools/audit_dashboard/`
client are scheduled for deletion by `EPIC-005` §3 and still present only until that teardown is
run. See [`.agents/context/tracing.md`](../../.agents/context/tracing.md) for what to use instead.

**The lesson, recorded because it is worth more than the feature was:** the repo's process
discipline was good — hundreds of passing tests, a bug-report workflow, doc-code-sync rules, a
clean mypy baseline — and a completely dead feature still shipped as done, because nobody ran it
end to end once. `scripts/verify_wheel_importable.py` now builds the wheel, installs it into a
throwaway venv, imports every shipped module, and resolves every declared console script
(`TASK-039`). That guard is the direct descendant of this file.

---

## 🎯 Goal
Provide a built-in Framework Observability & Diagnostics Extension (`AuditExtension`) that inspects live engine runtime telemetry via `IEngineContext` and renders a real-time interactive terminal dashboard (CLI Inspector) or JSON telemetry audit log.

---

## 🏛️ Background & Motivation
As applications grow (Trading Bots, IoT systems, Desktop Apps), developers need clear visibility into:
1. Which Extensions / Modules are loaded in the Engine.
2. Which `IHostedService` instances are currently RUNNING.
3. Which Background Tasks (`ITaskHandle`) are active, pending, or completed.
4. Total thread count, uptime, and system health status (`HealthCheckQuery`).

---

## 📐 Architecture & Design

### 1. `AuditExtension` Class
Location: `sagittarius_engine/extensions/audit/audit_extension.py`

```python
from sagittarius_engine.interfaces import IEngineContext, IExtension


class AuditExtension(IExtension):
    def register(self, ctx: IEngineContext) -> None:
        ctx.container.singleton(AuditService, AuditService(ctx))

    def boot(self, ctx: IEngineContext) -> None:
        if self.enable_dashboard:
            ctx.container.resolve(AuditService).start_server()
```

### 2. `AuditService` Core Inspector
Location: `sagittarius_engine/extensions/audit/audit_service.py`

Gathers telemetry directly from `IEngineContext`:
- `get_loaded_extensions() -> list[str]`
- `get_running_hosted_services() -> list[dict]`
- `get_active_tasks() -> list[dict]` (Iterates `context.tasks.tasks` returning ID, Name, Status, Runtime)
- `get_system_health() -> dict` (Dispatches `HealthCheckQuery`)

### 3. `AuditTerminalDashboard` (Remote Client TUI)
Location: `sagittarius_engine/extensions/audit/terminal_dashboard.py`

Uses a **Client-Server Architecture**. 
- `AuditService` hosts a background HTTP Server (port 9999) serving JSON telemetry.
- The `AuditTerminalDashboard` is a standalone CLI client that uses the `textual` framework to render a beautiful 5-Tab TUI.
- Users open a separate terminal to run the dashboard: `python -m sagittarius_engine.extensions.audit.terminal_dashboard`, avoiding stdout log overlap!
 🧵 TASKS:
    - [c4f81a9c] TerminalUI           (RUNNING)   [00:08:15]
    - [a1b2c3d4] AsyncGPAPipeline     (COMPLETED) [00:00:02]
================================================================================
```

---

## 📋 Implementation Checklist
- [ ] Create `sagittarius_engine/extensions/audit/` package.
- [ ] Implement `AuditService` querying `IEngineContext`.
- [ ] Implement `AuditExtension` implementing `IExtension`.
- [ ] Implement `AuditTerminalDashboard` CLI inspector.
- [ ] Write unit tests in `tests/test_audit_extension.py`.
