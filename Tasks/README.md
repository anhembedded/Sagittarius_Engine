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
| **TASK-015** | Framework Logging & Null Object Pattern | Core Architecture / Observability | 2026-08-04 | [TASK-015_framework_logging_null_object.md](completed/TASK-015_framework_logging_null_object.md) |
| **TASK-007** | Kernel Reliability and OSS Readiness | Reliability / Open Source Polish | 2026-08-04 | [TASK-007_kernel_reliability_oss_readiness.md](completed/TASK-007_kernel_reliability_oss_readiness.md) |
| **TASK-008** | Context Decoupling Program | Core Architecture / Service Boundaries | 2026-08-04 | [TASK-008_context_decoupling_program.md](completed/TASK-008_context_decoupling_program.md) |
| **TASK-018** | Record `BaseCard` Sub-Type Candidates (No Code Yet) | UI Engine / Widget Kit | 2026-08-23 | [TASK-018_baseCard_subtype_candidate_notes.md](completed/TASK-018_baseCard_subtype_candidate_notes.md) |

### 🟡 In Progress (`Tasks/in_progress/`)

*(No standalone in-progress tasks — active work is tracked inside the Epics below.)*

### 🔵 Backlog (`Tasks/backlog/`)

| Task ID | Title | Category | Priority | Spec File |
| --- | --- | --- | --- | --- |
| **TASK-016** | Formalize `name` Method on Interfaces | Core Architecture / Interfaces | P3 - Low | [TASK-016_interface_name_property.md](backlog/TASK-016_interface_name_property.md) |
| **TASK-017** | Production Readiness Hardening | Reliability / Security | P1 - Critical | [TASK-017_production_readiness_hardening.md](backlog/TASK-017_production_readiness_hardening.md) |
| **TASK-019** | `DatabaseExtension` exposes no way to reach the raw `Engine` | Extensions / Persistence | P2 | [TASK-019_database_extension_expose_engine.md](backlog/TASK-019_database_extension_expose_engine.md) |

---

## 🏛️ Epics — Multi-Task Programs

Full detail lives in each epic's own `README.md` under `Tasks/epics/` — see
[`Tasks/epics/README.md`](epics/README.md) for the directory convention. Only a one-line
link is kept here; content is not duplicated.

| ID | Name | Status |
| :--- | :--- | :---: |
| **[EPIC-001](epics/EPIC-001_ui_engine_foundation/README.md)** | UI Engine Foundation — tokens, widget kit, composition runtime for `pyside_mvc` | 🟡 In Progress (3/4 subtasks done) |
| **[EPIC-002](epics/EPIC-002_engine_sample_app_and_doc_rewrite/README.md)** | Engine Sample App & Doc Rewrite — replace the stale `.agents/context/` snapshot with docs grounded in a real, running sample app | 🟡 In Progress (0/4 subtasks done) |

---

## 📂 Directory Layout

```
Tasks/
├── README.md                           # Master Kanban Board & Overview
├── backlog/                            # Planned Task Specifications & Proposals
│   ├── TASK-016_interface_name_property.md
│   └── TASK-017_production_readiness_hardening.md
├── epics/                               # Multi-task programs — see epics/README.md
│   └── EPIC-001_ui_engine_foundation/
│       ├── README.md
│       ├── completed/
│       │   ├── EPIC-001A_architecture_rule_rewrite.md
│       │   ├── EPIC-001B_design_token_layer.md
│       │   └── EPIC-001C_widget_kit_expansion.md
│       └── incomplete/
│           └── EPIC-001D_runtime_slot_registry.md
├── issue-report/                       # High-impact Architecture Issue Report
│   ├── issue.md
│   └── exception_case.md
├── in_progress/                        # Actively Worked On Specifications (standalone tasks only)
├── completed/                          # Finished Tasks & Historical Docs
│   ├── TASK-001_background_service.md
│   ├── TASK-002_audit_extension.md
│   ├── TASK-009_exception_case_test_coverage.md
│   ├── TASK-010_async_lifecycle_support.md
│   ├── TASK-011_strict_extension_adapter_typing.md
│   ├── TASK-012_di_container_scoped_lifecycle.md
│   ├── TASK-013_engine_context_god_object_prevention.md
│   ├── TASK-014_cqrs_type_safety_overload.md
│   ├── TASK-015_framework_logging_null_object.md
│   ├── TASK-016_interface_name_property.md
│   ├── TASK-007_kernel_reliability_oss_readiness.md
│   ├── TASK-008_context_decoupling_program.md
│   └── TASK-018_baseCard_subtype_candidate_notes.md
```
