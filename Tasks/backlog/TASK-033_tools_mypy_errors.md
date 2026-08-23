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
> Only the name clash remains open.

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
