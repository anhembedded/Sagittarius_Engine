# TASK-041: Re-probe `REF-001`'s 11 cycle-claimed local imports under real import orders

- **Status**: 🔵 Backlog
- **Category**: Core Architecture / Tech Debt
- **Priority**: P3
- **Filed by**: [`REF-001`](../refix/completed/REF-001_function_local_imports_rule_vs_code.md) §2.3/§5

---

## 🎯 Summary & Objectives

`REF-001` bounded eleven function-local imports whose comments claim they break an import
cycle (`kernel/context.py` ×6, `infrastructure/config/config_manager.py` ×3,
`kernel/module_auto_discovery.py`, `extensions/diagnostics/runtime.py`). All eleven hoist
cleanly **in isolation** — a fresh interpreter, `import <target>` first, then
`import <module>`. That is recorded in `SANCTIONED_LOCAL_IMPORTS`
(`tests/test_architecture.py`) as evidence for "not obviously cyclic," explicitly **not**
as proof of "no cycle": a single fresh-interpreter probe cannot see an order-dependent
cycle that only manifests when a real application's own import sequence runs first.

This task is the stricter check `REF-001` §2.3 left open, so that each row is retired on
real evidence rather than left in the allowlist by default.

## 📐 Implementation Plan / Overview

1. For each of the 11 sites, hoist the import to module scope.
2. Run it against every import order that actually occurs, not one: the full `pytest`
   suite (which imports modules in whatever order test collection produces), plus
   `examples/student_management`'s `main.py` and `gui.py` entry points, plus
   `sagittarius-doctor` against `doctor_target:build`. A hoist that survives all three is
   real evidence a fresh-interpreter probe cannot give.
3. For any site that still fails under one of those orders, leave it in
   `SANCTIONED_LOCAL_IMPORTS` with the *actual* cycle now documented at the import (which
   two modules, and which import triggers which) — replacing the "comment claims a cycle"
   language `REF-001` left as a placeholder.
4. For any site that survives all three, hoist it for real and remove its row from
   `SANCTIONED_LOCAL_IMPORTS` — `test_every_sanctioned_local_import_still_exists()` will
   fail until the row is removed, which is the guard doing its job.

## 🧪 Verification & Test Coverage

- `pytest tests/test_architecture.py` — the allowlist and the code must agree either way.
- `pytest tests/` (full suite), `run.ps1` (both GUI backends), `sagittarius-doctor` — the
  three real import orders from step 2, each run against every hoisted candidate.
