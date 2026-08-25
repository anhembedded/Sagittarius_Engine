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
| **TASK-029** | `TASK-024`'s `sdk/` deletion left stale "SDK" references in 5 `.agents/` files | Documentation / Doc-Code Sync | 2026-08-23 | [TASK-029_sdk_deletion_left_stale_docs.md](completed/TASK-029_sdk_deletion_left_stale_docs.md) |
| **TASK-026** | `PydanticValidationMiddleware` no longer silently skips validation on hint-resolution failure | Middleware / Correctness | 2026-08-23 | [TASK-026_validation_middleware_silently_self_disables.md](completed/TASK-026_validation_middleware_silently_self_disables.md) |
| **TASK-030** | `scripts/ci-local.ps1` — log capture, full-run, machine-readable summary (matches Elite) | Build / Developer Experience | 2026-08-23 | [TASK-030_ci_local_script_matching_elite_pattern.md](completed/TASK-030_ci_local_script_matching_elite_pattern.md) |
| **TASK-032** | mypy baseline cleared — `Success: no issues found in 259 source files`, gate `RESULT: PASS` | Kernel / Typing / Tech Debt | 2026-08-23 | [TASK-032_mypy_baseline_cleanup.md](completed/TASK-032_mypy_baseline_cleanup.md) |
| **TASK-017** | Production Readiness Hardening — 7 reliability/security issues + 7 regression tests | Reliability / Security | 2026-08-23 | [TASK-017_production_readiness_hardening.md](completed/TASK-017_production_readiness_hardening.md) |
| **TASK-027** | `py.typed` marker shipped (PEP 561) + stale-wheel packaging defect fixed | Packaging / Typing | 2026-08-23 | [TASK-027_no_py_typed_marker.md](completed/TASK-027_no_py_typed_marker.md) |
| **TASK-022** | `LICENSE` file added (MIT) and verified present in wheel + sdist | Packaging / Legal | 2026-08-23 | [TASK-022_missing_license_file.md](completed/TASK-022_missing_license_file.md) |
| **TASK-021** | ruff config consolidated, `examples/`+`tools/` added to CI lint scope, local toolchain pins bumped to the verified-clean versions | Build / Tooling | 2026-08-23 | [TASK-021_ruff_config_shadowing.md](completed/TASK-021_ruff_config_shadowing.md) |
| **TASK-020** | CI benchmark job's stale path fixed; runs and produces real output again | CI / Build | 2026-08-23 | [TASK-020_ci_benchmark_job_stale_path.md](completed/TASK-020_ci_benchmark_job_stale_path.md) |
| **TASK-023** | CI matrix/`requires-python` rule written into `release.md`; the `ITaskHandle` story it exists to prevent recorded | CI / Compatibility | 2026-08-23 | [TASK-023_ci_matrix_hides_312_313_breakage.md](completed/TASK-023_ci_matrix_hides_312_313_breakage.md) |
| **TASK-028** | Gate false-positive fixed + regression test added + ONBOARDING PATH guidance corrected | Build / Tooling — Completion Gate | 2026-08-23 | [TASK-028_pre_commit_gate_false_positive_on_missing_tool.md](completed/TASK-028_pre_commit_gate_false_positive_on_missing_tool.md) |
| **TASK-031** | Root package no longer imports any extension; incomplete original diagnosis corrected mid-fix | Architecture / Package Boundaries | 2026-08-23 | [TASK-031_top_level_package_eagerly_imports_persistence.md](completed/TASK-031_top_level_package_eagerly_imports_persistence.md) |
| **TASK-033** | `audit_dashboard.py` renamed to `audit_dashboard_cli.py`; the documented app is reachable under its own name again | Tooling / Package Boundaries | 2026-08-23 | [TASK-033_tools_mypy_errors.md](completed/TASK-033_tools_mypy_errors.md) |
| **TASK-037** | `IView` dual QML/QWidget rendering backend — enroll-form prototype validated, then rolled out to the full roster screen (`WidgetRosterView`, `run.ps1 -QtWidget`) | Architecture / Presentation Layer | 2026-08-23 | [TASK-037_iview_dual_backend_prototype_validated.md](completed/TASK-037_iview_dual_backend_prototype_validated.md) |
| **TASK-038** | `pyside_mvc.widgets` — QtWidgets base classes (`Surface`/`Card`/`Panel`/`Overlay`/`Styled*`) replacing the QML kit, built for Elite's `EPIC-006` (drop QML project-wide) | Architecture / Presentation Layer | 2026-08-24 | [TASK-038_qtwidgets_base_classes_surface_overlay_controls.md](completed/TASK-038_qtwidgets_base_classes_surface_overlay_controls.md) |
| **TASK-034** | `extensions/__init__.py` barrel made lazy (PEP 562 `__getattr__`) — deep-importing one extension no longer pulls in its five siblings | Architecture / Package Boundaries | 2026-08-24 | [TASK-034_extensions_barrel_eager_imports_everything.md](completed/TASK-034_extensions_barrel_eager_imports_everything.md) |
| **TASK-039** | Wheel guard now resolves every advertised console script; caught `sagittarius-audit`, which has never run since `TASK-002` and is removed rather than repaired | Build / Packaging — Release Gate | 2026-08-25 | [TASK-039_wheel_guard_never_checked_console_scripts.md](completed/TASK-039_wheel_guard_never_checked_console_scripts.md) |

### 🟡 In Progress (`Tasks/in_progress/`)

*(No standalone in-progress tasks — active work is tracked inside the Epics below.)*

### 🔵 Backlog (`Tasks/backlog/`)

| Task ID | Title | Category | Priority | Spec File |
| --- | --- | --- | --- | --- |
| **TASK-035** | `AppDataTable`'s columns render with no horizontal gap — a right-aligned column touches the next one | UI / Widget Kit (`pyside_mvc`) | P3 | [TASK-035_appdatatable_columns_have_no_horizontal_gap.md](backlog/TASK-035_appdatatable_columns_have_no_horizontal_gap.md) |
| **TASK-036** | Audit every widget-kit card for missing Windows-Explorer-style utility actions (survey done, decisions/implementation pending) | UI / Widget Kit (`pyside_mvc`) | P2 | [TASK-036_audit_widget_kit_for_missing_windows_style_actions.md](backlog/TASK-036_audit_widget_kit_for_missing_windows_style_actions.md) |

---

## 🐞 Bugs

Defects are tracked separately on the **[Bug Board](bug_report/README.md)** (`BUG-XXX`), so that
*open* bugs are visible somewhere — this board only ever shows a bug once it's been fixed and
becomes a completed task. Bugs are **not** counted in the task numbers above.

See that board's own Overview table for the current open count — don't trust a number copied
here, it drifts. Same convention as `Sagittarius_Elite_Warrior/Tasks/bug_report/`, independent
board.

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
| **[EPIC-003](epics/EPIC-003_database_extension_multi_db/README.md)** | `DatabaseExtension` Multi-Database Support — named/sharded databases via `IDatabaseManager`, supersedes `TASK-019` | ✅ Completed 2026-08-23 (4/4 subtasks done) |
| **[EPIC-004](epics/EPIC-004_sqlite_shard_manager_and_elite_migration/README.md)** | Sharded-SQLite Manager & Elite Migration — absorb the consuming app's generic sharding layer into the engine, then migrate it onto it | ✅ Completed 2026-08-23 (3/3 subtasks done) |
| **[EPIC-005](epics/EPIC-005_audit_telemetry_rebuild/README.md)** | Audit Telemetry Teardown & Trace Recorder — both dashboard clients are 100% non-functional; delete them and the server, rebuild the recorder half of SystemView, export to Perfetto/OpenTelemetry rather than building a timeline UI. Supersedes `TASK-002` | ⏸️ On hold — spec complete, deferred behind `EPIC-006` |
| **[EPIC-006](epics/EPIC-006_wiring_and_readiness_diagnostics/README.md)** | Wiring & Readiness Diagnostics — join `EventRegistry` (declared) against `IEventBus` (subscribed) to catch mis-wiring at boot, plus an explicit `app.ready` milestone. Catches the silent-typo class nothing else can | 🟡 In Progress (1/6 subtasks done) |

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
