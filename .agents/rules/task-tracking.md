---
name: Task Tracking
description: Kanban board layout, epic/subtask conventions, and task lifecycle for Tasks/. Load for complex multi-phase work.
trigger: model_decision
---

# Rules: Task Tracking

> Context: This project uses a centralized task management hub located in the `Tasks/` directory to organize framework roadmap items, architectural proposals, active work items, and completion records using an enterprise Kanban layout.

---

## Kanban Board & Directory Structure

The central source of truth for all tasks is `Tasks/README.md`. 
The `Tasks/` directory is structured as follows:

* `Tasks/backlog/`: Planned Task Specifications & Proposals
* `Tasks/in_progress/`: Actively Worked On Specifications
* `Tasks/completed/`: Finished Tasks & Historical Docs
* `Tasks/issue-report/`: High-impact Architecture Issue Reports
* `Tasks/epics/`: Multi-task programs — see below

## Task Lifecycle & Agent Responsibilities

When starting or finishing a complex task, you MUST follow this workflow:

### 1. Starting a Task
If the user assigns you a new task or asks you to work on an existing task from the backlog:
- **Move/Create the Task File**: Move the corresponding `TASK-XXX_name.md` file from `Tasks/backlog/` to `Tasks/in_progress/` (or create a new one in `in_progress/` if it's a new complex task).
- **Update the Kanban Board**: Edit `Tasks/README.md` to move the row from the `Backlog` table to the `In Progress` table. Ensure you update the relative links in the table!
- **File Naming**: Use the format `TASK-XXX_short_description.md` (e.g., `TASK-001_background_service.md`).

### 2. Task File Format
The task file should follow this structure:
```markdown
# TASK-XXX: [Title]

- **Status**: 🔄 In Progress (or ✅ Completed)
- **Category**: [Category]
- **Started Date**: YYYY-MM-DD

---

## 🎯 Summary & Objectives
[Brief description of the task]

## 📐 Implementation Plan / Overview
[Details about the planned or completed implementation, key decisions, files changed]

## 🧪 Verification & Test Coverage
[How this was/will be tested]
```

### 3. Completing a Task
When you finish implementing and verifying the task:
- **Move the Task File**: Move the task file from `Tasks/in_progress/` to `Tasks/completed/`.
- **Update Task File Metadata**: Inside the file, change the `Status` to `✅ Completed` and add `Completed Date: YYYY-MM-DD`.
- **Update the Kanban Board**: Edit `Tasks/README.md` to move the task from the `In Progress` table to the `Completed` table. Update the relative link to point to `completed/TASK-XXX_...md`.

---

## Epics — Multi-Task Programs

Adopted 2026-08-22 (ported from `Sagittarius_Elite_Warrior`'s `Tasks/epics/` convention).
When a body of work has **several subtasks and several rounds of status updates**, it does
not belong as a single flat file in `Tasks/backlog/`, and it does not belong inline in
`Tasks/README.md` either — both become hard to read once a program has real internal
structure.

Instead it gets its own directory: `Tasks/epics/EPIC-XXX_slug/`, containing the epic's own
`README.md` (objective, context, subtask table) plus `incomplete/`/`completed/` subtask
files (`EPIC-XXXA_name.md`, `EPIC-XXXB_name.md`, …). Full convention:
[`Tasks/epics/README.md`](../../Tasks/epics/README.md).

`Tasks/README.md` keeps only a **one-line link** to each epic's `README.md` — never a copy
of its content. `EPIC-XXX` is its own ID pool, independent of `TASK-XXX`.

Use this structure when a task would otherwise need `## Subtask 1`, `## Subtask 2`, …
headings inside one file, or when the work is expected to span multiple sessions with
distinct completion points. A single-session, single-deliverable task stays a plain
`TASK-XXX` file — do not create an epic directory for it.

---

## When to Use Tracking (Complexity Gate)

**Create a tracking file ONLY when the task meets one or more of these criteria:**
* **Multi-session / Large Scope:** Task touches multiple domains/modules or spans a significant architecture change.
* **Roadmap Items:** The task is part of the project's official backlog (`Tasks/backlog/`).

**Do NOT create tracking files for:**
* Trivial bug fixes, formatting, or single-file changes.
* Purely investigative tasks.
