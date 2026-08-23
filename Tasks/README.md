# 📋 Sagittarius Engine - Project Task Hub & Kanban Board

Welcome to the central task management hub for **Sagittarius Engine**. This directory organizes framework roadmap items, architectural proposals, active work items, and completion records using an enterprise Kanban layout.

---

## 📊 Kanban Board

### 🟢 Completed (`Tasks/completed/`)

| Task ID | Title | Category | Completed Date | Spec File |
| --- | --- | --- | --- | --- |
| **TASK-001** | `BackgroundService` Pattern | Architecture / Hosted Services | 2026-07-28 | [TASK-001_background_service.md](completed/TASK-001_background_service.md) |
| **TASK-002** | `AuditExtension` & CLI Inspector | Observability / Diagnostics | 2026-07-28 | [TASK-002_audit_extension.md](completed/TASK-002_audit_extension.md) |
| **TASK-009** | Exception-Case Test Coverage Expansion | Testing & Quality Assurance | 2026-07-30 | [TASK-009_exception_case_test_coverage.md](completed/TASK-009_exception_case_test_coverage.md) |
| **TASK-010** | Async Lifecycle Support | Core Architecture / Concurrency | 2026-08-02 | [TASK-010_async_lifecycle_support.md](completed/TASK-010_async_lifecycle_support.md) |
| **TASK-011** | Strict Extension Adapter Typing | Core Architecture / Robustness | 2026-08-02 | [TASK-011_strict_extension_adapter_typing.md](completed/TASK-011_strict_extension_adapter_typing.md) |
| **TASK-012** | DI Container Scoped Lifecycle | Infrastructure / Dependency Injection | 2026-08-02 | [TASK-012_di_container_scoped_lifecycle.md](completed/TASK-012_di_container_scoped_lifecycle.md) |
| **TASK-013** | Engine Context God Object Prevention | Core Architecture / Clean Architecture | 2026-08-02 | [TASK-013_engine_context_god_object_prevention.md](completed/TASK-013_engine_context_god_object_prevention.md) |
| **TASK-015** | Framework Logging Null Object | Core Architecture / Observability | 2026-08-04 | [TASK-015_framework_logging_null_object.md](completed/TASK-015_framework_logging_null_object.md) |
| **TASK-016** | Formalize `name` property | Core Architecture / Clean Code | 2026-08-04 | [TASK-016_interface_name_property.md](completed/TASK-016_interface_name_property.md) |
| **TASK-014** | CQRS Dispatcher Type Safety (TOutput Resolution) | Core Architecture / Type Safety | 2026-08-02 | [TASK-014_cqrs_type_safety_overload.md](completed/TASK-014_cqrs_type_safety_overload.md) |
| **TASK-007** | Kernel Reliability and OSS Readiness | Reliability / Open Source Polish | 2026-08-04 | [TASK-007_kernel_reliability_oss_readiness.md](completed/TASK-007_kernel_reliability_oss_readiness.md) |
| **TASK-008** | Context Decoupling Program | Core Architecture / Service Boundaries | 2026-08-04 | [TASK-008_context_decoupling_program.md](completed/TASK-008_context_decoupling_program.md) |
| **TASK-018** | Record `BaseCard` Sub-Type Candidates (No Code Yet) | UI Engine / Widget Kit | 2026-08-23 | [TASK-018_baseCard_subtype_candidate_notes.md](completed/TASK-018_baseCard_subtype_candidate_notes.md) |
| **TASK-024** | Scaffolding feature removed (both commands were broken; feature unused) | SDK / Developer Experience | 2026-08-23 | [TASK-024_getting_started_scaffolders_broken.md](completed/TASK-024_getting_started_scaffolders_broken.md) |
| **TASK-025** | Dead `infrastructure/persistence/` deleted + import guard test added | Infrastructure / Cleanup | 2026-08-23 | [TASK-025_dead_infrastructure_persistence_package.md](completed/TASK-025_dead_infrastructure_persistence_package.md) |
| **TASK-026** | `PydanticValidationMiddleware` no longer silently skips validation on hint-resolution failure | Middleware / Correctness | 2026-08-23 | [TASK-026_validation_middleware_silently_self_disables.md](completed/TASK-026_validation_middleware_silently_self_disables.md) |
| **TASK-030** | `scripts/ci-local.ps1` — log capture, full-run, machine-readable summary (matches Elite) | Build / Developer Experience | 2026-08-23 | [TASK-030_ci_local_script_matching_elite_pattern.md](completed/TASK-030_ci_local_script_matching_elite_pattern.md) |

### 🟡 In Progress (`Tasks/in_progress/`)

| Task ID | Title | Category | Priority | Spec File |
| --- | --- | --- | --- | --- |
| **TASK-017** | Production Readiness Hardening | Reliability / Security | P1 - Critical | [TASK-017_production_readiness_hardening.md](in_progress/TASK-017_production_readiness_hardening.md) |

### 🔵 Backlog (`Tasks/backlog/`)

| Task ID | Title | Category | Priority | Spec File |
| --- | --- | --- | --- | --- |
| **TASK-019** | `DatabaseExtension` exposes no way to reach the raw `Engine` | Extensions / Persistence | P2 | [TASK-019_database_extension_expose_engine.md](backlog/TASK-019_database_extension_expose_engine.md) |
| **TASK-020** | CI `benchmark` job runs a moved path, masked by `continue-on-error` | CI / Build | P3 | [TASK-020_ci_benchmark_job_stale_path.md](backlog/TASK-020_ci_benchmark_job_stale_path.md) |
| **TASK-021** | `ruff.toml` shadows `pyproject.toml` — the intended rule set never runs | Build / Tooling | P2 | [TASK-021_ruff_config_shadowing.md](backlog/TASK-021_ruff_config_shadowing.md) |
| **TASK-022** | Package declares MIT but ships no `LICENSE` file | Packaging / Legal | P2 | [TASK-022_missing_license_file.md](backlog/TASK-022_missing_license_file.md) |
| **TASK-023** | CI's single-version matrix is the blind spot (version range now narrowed to 3.14) | CI / Compatibility | P3 | [TASK-023_ci_matrix_hides_312_313_breakage.md](backlog/TASK-023_ci_matrix_hides_312_313_breakage.md) |
| **TASK-027** | Engine ships no `py.typed` — consumers get zero type information | Packaging / Typing | P2 | [TASK-027_no_py_typed_marker.md](backlog/TASK-027_no_py_typed_marker.md) |
| **TASK-028** | Gate silent-false-positive fixed by `TASK-030`; regression test + doc-accuracy recheck remain | Build / Tooling — Completion Gate | P3 | [TASK-028_pre_commit_gate_false_positive_on_missing_tool.md](backlog/TASK-028_pre_commit_gate_false_positive_on_missing_tool.md) |
| **TASK-029** | `TASK-024`'s `sdk/` deletion left stale "SDK" references in 5 `.agents/` files | Documentation / Doc-Code Sync | P3 | [TASK-029_sdk_deletion_left_stale_docs.md](backlog/TASK-029_sdk_deletion_left_stale_docs.md) |

---

## 🐞 Bugs

Defects are tracked separately on the **[Bug Board](bug_report/README.md)** (`BUG-XXX`), so that
*open* bugs are visible somewhere — this board only ever shows a bug once it's been fixed and
becomes a completed task. Bugs are **not** counted in the task numbers above.

Currently **3 open**, all found in the 2026-08-23 post-`EPIC-002` audit. Same convention as
`Sagittarius_Elite_Warrior/Tasks/bug_report/`, independent board.

Rule of thumb: **BUG** = something is wrong or states something untrue; **TASK** = something is
missing or should change.

---

## 🏛️ Epics — Multi-Task Programs

Full detail lives in each epic's own `README.md` under `Tasks/epics/` — see
[`Tasks/epics/README.md`](epics/README.md) for the directory convention. Only a one-line
link is kept here; content is not duplicated.

| ID | Name | Status |
| :--- | :--- | :---: |
| **[EPIC-001](epics/EPIC-001_ui_engine_foundation/README.md)** | UI Engine Foundation — tokens, widget kit, composition runtime for `pyside_mvc` | 🟡 In Progress (3/4 subtasks done) |
| **[EPIC-002](epics/EPIC-002_engine_sample_app_and_doc_rewrite/README.md)** | Engine Sample App & Doc Rewrite — replace the stale `.agents/context/` snapshot with docs grounded in a real, running sample app | ✅ Completed 2026-08-23 (4/4 subtasks done) |

---

## 📂 Directory Layout

```
Tasks/
├── README.md                           # Master Kanban Board & Overview
├── backlog/                            # Planned Task Specifications & Proposals
│   └── ... one file per TASK-XXX (see the Backlog table above)
├── epics/                               # Multi-task programs — see epics/README.md
│   ├── EPIC-001_ui_engine_foundation/
│       ├── README.md
│       ├── completed/
│       │   ├── EPIC-001A_architecture_rule_rewrite.md
│       │   ├── EPIC-001B_design_token_layer.md
│       │   └── EPIC-001C_widget_kit_expansion.md
│       └── incomplete/
│           └── EPIC-001D_runtime_slot_registry.md
├── bug_report/                         # 🐞 Bug Board — see bug_report/README.md
│   ├── README.md                       #    open + fixed tables, BUG-vs-TASK guidance
│   ├── incomplete/                     #    BUG-XXX not yet fixed (new bugs start here)
│   └── completed/                      #    BUG-XXX fixed, with evidence
├── issue-report/                       # High-impact Architecture Issue Report
│   └── issue.md
├── in_progress/                        # Actively Worked On Specifications (standalone tasks only)
└── completed/                          # Finished Tasks & Historical Docs
    └── ... one file per TASK-XXX (see the Completed table above)
```
