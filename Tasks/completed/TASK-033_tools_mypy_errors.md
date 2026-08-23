# TASK-033: `tools/` ships two different apps under the name `audit_dashboard`

> **Rescoped 2026-08-23.** This task was originally filed to triage 9 mypy errors in `tools/`
> *and* record the name clash below. The mypy half is **done and no longer part of this task** —
> it was fixed concurrently as part of `TASK-021`, and `tools/` is now in the mypy scope of both
> `.github/workflows/ci.yml` and `scripts/ci-local.ps1`. Verified on the repo's pinned toolchain
> (`ruff==0.16.4`, `mypy==2.3.1`): `mypy tools --ignore-missing-imports --follow-imports=skip`
> reports `Success: no issues found in 13 source files`, and the full CI scope
> (`sagittarius_engine tests examples tools`) reports `Success: no issues found in 330 source
> files`. The original 9-error reading was taken under `mypy 2.1.0` before that fix landed.
>
> **Fully closed 2026-08-23.**
>
> - **Req 1 — renamed** `tools/audit_dashboard.py` → `tools/audit_dashboard_cli.py`, over the
>   other two options. Deleting was rejected: the file still works as a standalone lightweight
>   viewer and nothing established it was dead code, only that it clashed. Adding `__init__.py`
>   to the directory was rejected per the bug's own reasoning — it flips resolution silently,
>   a behaviour change disguised as a cleanup. Renaming is the only option that disambiguates
>   without changing what either app does.
>
>   Supporting evidence for choosing the `.py` file as the one to move, not the directory:
>   `git log` shows the directory's PySide6/WebSocket app arrived via a later commit
>   (`f0247bd`, "refactor telemetry to use websockets and integrate PySide6 dashboard") —
>   the `.py` file's `urllib.request.urlopen` HTTP-GET polling is the older mechanism the
>   WebSocket-based `ITelemetryBroadcaster`/`WebsocketBroadcaster` superseded. Both
>   `architecture.md` and `configuration.md` already exclusively documented the directory as
>   canonical, and only the directory has a launcher (`run_dashboard.ps1`) — the `.py` file has
>   neither. Whether the renamed CLI script still actually connects successfully against the
>   current WebSocket-based telemetry endpoint was not verified (a plain HTTP GET against a
>   WebSocket server would not get a valid response) — noted honestly rather than claimed;
>   out of scope for a rename.
> - **Verified the fix, not just the rename:** `import audit_dashboard` from `tools/` now
>   resolves to the directory (`audit_dashboard.__path__` points at
>   `tools/audit_dashboard/`), and `from audit_dashboard.Domain import entities` resolves
>   correctly — the app the architecture docs describe is now actually reachable under its own
>   name.
> - **Req 2 — nothing to update.** Neither `architecture.md` nor `configuration.md` ever
>   referenced the `.py` file (both already named only the directory), so the rename introduces
>   no doc drift. `ruff`/`mypy`/format all still pass on the renamed file.

## Description

`tools/` contains **both** a module and a directory with the same name, and they are two
different applications:

- **`tools/audit_dashboard.py`** — a `rich`-based terminal dashboard (argparse, `urllib.request`,
  `rich.live.Live`).
- **`tools/audit_dashboard/`** — the PySide6 desktop app that
  `.agents/context/architectures/architecture.md` documents as this repo's Clean Architecture
  reference, naming `Domain/entities.py`, `Domain/ports.py`,
  `application/receive_audit_use_case.py`, `infra/websocket_connector.py` and
  `presentation/main_window.py`.

**`import audit_dashboard` resolves to the `.py` module, not the package** — measured
2026-08-23 from `tools/`:

```
>>> import audit_dashboard; audit_dashboard.__file__
'...\\tools\\audit_dashboard.py'
```

## Why it resolves that way — the counter-intuitive part

The usual expectation is that a package shadows a same-named module. That is true for a
**regular** package, but `tools/audit_dashboard/` has **no `__init__.py`**, so it is a
**namespace** package — and namespace packages rank *below* regular modules in `sys.path`
resolution. A regular module therefore wins.

The consequence: the directory the architecture docs treat as canonical is unreachable under its
own name. It works today only because it is launched by path
(`tools/audit_dashboard/main.py`, `run_dashboard.ps1`) rather than imported.

## Why it matters

Nothing is broken right now, which is exactly what makes it a landmine — the same shape as
[`TASK-025`](../completed/TASK-025_dead_infrastructure_persistence_package.md)'s dead package,
which sat harmless until the first consumer tried to import it and got a confusing error about a
file that had not existed for months.

The specific hazard here is worse than an ImportError, because there is no error at all: anyone
who writes `import audit_dashboard` intending the documented Clean Architecture app silently gets
a completely different program.

## Requirements

1. Decide deliberately between:
   - **Rename one of the two.** Cleanest — the two apps genuinely have different jobs, and one
     name for both was never intentional.
   - **Add `__init__.py` to the package.** This flips resolution, so `import audit_dashboard`
     would start returning the *other* application. That is a **behaviour change, not a
     cleanup** — anything currently importing the module by name would silently switch programs.
   - **Delete whichever is obsolete**, if one of them is.
2. Whichever is chosen, update `.agents/context/architectures/architecture.md` and
   `.agents/context/configuration.md`, which both reference `audit_dashboard` paths, so the docs
   name the thing that actually resolves (`rules/doc-code-sync.md`).

## Priority

P3 — no runtime impact today; `tools/` is not part of the installable package
(`ONBOARDING.md` §2: "Standalone utilities on top of the engine"), so this reaches no consumer.

## Category

Tooling / Package Boundaries

## Related

- [TASK-021](../completed/TASK-021_ruff_config_shadowing.md) — brought `examples/` and `tools/`
  into the lint and type-check scope; this was found while doing that work.
- [TASK-025](../completed/TASK-025_dead_infrastructure_persistence_package.md) — the same
  "harmless until someone imports it" shape.
