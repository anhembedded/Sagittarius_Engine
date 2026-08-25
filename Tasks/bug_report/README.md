# 🐞 Bug Board — Sagittarius Engine

Tracks **every reported defect** in the engine. Kept separate from
[`../README.md`](../README.md) for the same reason the app repo does it: that board tracks
*work items* (`TASK-XXX`, `EPIC-XXX`) — a fixed bug shows up in its Completed section, but an
**open** bug had nowhere to be listed at all. To know what the engine is currently carrying,
you'd have to open every file. This board is the answer to that question.

Convention mirrors `Sagittarius_Elite_Warrior/Tasks/bug_report/` deliberately, so the same
habit works in both repos — but the two boards are **independent**, like the repos themselves
(see `.agents/ONBOARDING.md` §8). Never file an engine bug on the app's board or vice versa.

- **Directory layout** (parallel to `Tasks/backlog|completed/` for tasks):
  - `incomplete/` — bugs **not yet fixed**. New bugs are always created here.
  - `completed/` — fixed bugs, with their own evidence.
- Name as `BUG-XXX_description.md`, numbering from the highest existing across **both**
  directories.
- **When fixed:** `git mv incomplete/BUG-XXX_*.md completed/`, update `Status` inside the file,
  then move its row in the tables below from Open to Fixed.
- Bugs are **not** counted in `../README.md`'s task numbers.

### BUG vs TASK — which one to file

- **BUG** — something is *wrong*: it does not work, or it states something untrue about the
  code. Regardless of size.
- **TASK** — something is *missing or should change*: a feature, a cleanup, a decision, a
  hardening program.

Borderline calls resolved so far: missing `LICENSE` is a `TASK` (nothing is wrong, something is
absent); a docstring naming a class that doesn't exist is a `BUG` (an active false statement).

> Updated: 2026-08-23 — board created during the post-EPIC-002 engine audit.

---

## 📊 Overview

| Status | Count |
| :--- | :---: |
| 🔴 **Open** | 2 |
| ✅ **Fixed** | 5 |
| 📈 **Total** | **7** |

`BUG-004` and `BUG-005` were found on 2026-08-24 during a cross-repo audit run for
`Sagittarius_Elite_Warrior`'s `EPIC-007`/`EPIC-008`. Both are defects in **this** repo, so
they are tracked, fixed and committed here — the app repo's epics only reference them
(`.agents/ONBOARDING.md` §8). Both closed 2026-08-25.

The three fixed ones were found on 2026-08-23 during the engine audit that followed `EPIC-002`. Defects
found in the *same* audit that already had a fix applied were tracked as tasks instead, because
they were closed in the same session — see `TASK-024`, `TASK-025`, and the `ITaskHandle` import
bug fixed in commit `568d3bb`. Future defects should come here first.

---

## 🔴 Open

| ID | Title | Severity | Reported | Note |
| :--- | :--- | :---: | :---: | :--- |
| **[BUG-007](incomplete/BUG-007_resilient_bus_drops_a_subscription_on_name_collision.md)** | `ResilientEventBus.on()` silently drops a subscription when two event classes share a `__name__` | Medium | 2026-08-25 | Keys `_wrapper_map` by `__name__` while the rest of the package keys by `event_name`/`__qualname__`; the colliding second `on()` early-returns and the handler never fires. Reproduced. Found while fixing `EPIC-008C`, filed separately rather than fixed inline. |
| **[BUG-006](incomplete/BUG-006_qml_warning_tests_are_order_dependent.md)** | The two "no QML runtime warnings" tests assert on the whole Qt message stream, so a once-per-process platform warning makes them order-dependent | Medium | 2026-08-25 | gallery-first → gallery fails; roster-first → both pass. Same code, opposite results. On Windows the contaminant is a `QFontDatabase` platform warning; **on Linux it is 32 `RosterScreen.qml` teardown `TypeError`s** that normally land after pytest's summary line and move inside the test when unrelated test files shift timing (found 2026-08-25 during `EPIC-007A`). Neither is a QML binding error the test was written to catch. |

---

## ✅ Fixed

| ID | Title | Severity | Reported | Note |
| :--- | :--- | :---: | :---: | :--- |
| **[BUG-004](completed/BUG-004_overlay_names_nonexistent_subclasses.md)** | `Overlay`'s docstring and `TypeError` message name `ConfirmOverlay`/`PickerOverlay`, which exist nowhere | Medium | 2026-08-24 | Fixed 2026-08-25: both written, one file per class under `widgets/overlays/`, exported from `__all__`. Closed by writing them rather than by dropping the mention — 9 real consumers were waiting in the app repo. The regression test resolves the names *out of the message itself*, so rewording cannot reintroduce a phantom. 1004 passed, coverage 89.46%. |
| **[BUG-005](completed/BUG-005_baseevent_inheritance_is_inert_for_dataclasses.md)** | Inheriting `BaseEvent` gave a `@dataclass` subclass nothing — `event_id`, `occurred_on`, `to_dict()` all raised `AttributeError` | High | 2026-08-24 | Fixed 2026-08-25: `BaseEvent` is now a `@dataclass` with `kw_only` metadata fields backed by concrete properties (a public dataclass field with the same name as the inherited abstract property re-triggers `abc.update_abstractmethods()` and breaks instantiation — avoided). `event_name` defaults via `__init_subclass__`. 8 new regression tests, all 3 existing engine consumers unaffected. |
| **[BUG-003](completed/BUG-003_get_logger_annotation_contradicts_iengincontext_contract.md)** | `_get_logger()` declared `ILogger \| None` against a contract that guarantees non-None | Low | 2026-08-23 | Fixed 2026-08-23: 4 mypy errors resolved (27→23). Also removed 6 dead `if logger:` guards in `bootstrap.py`, by explicit user decision. 757 passed, 0 failed. |
| **[BUG-001](completed/BUG-001_phantom_apprunner_in_iengincontext_docstring.md)** | `IEngineContext` docstring names a nonexistent `AppRunner` class | Low | 2026-08-23 | Fixed 2026-08-23: mention dropped (not renamed) — `ApplicationRunner` takes no context at all, per its real constructor. `doc-code-sync.md:63`'s row marked closed in place. |
| **[BUG-002](completed/BUG-002_mkdocs_config_points_at_deleted_docs_tree.md)** | `mkdocs.yml` builds from a `docs/` tree deleted in `a338d42` | Medium | 2026-08-23 | Fixed 2026-08-23: Option A chosen — `mkdocs.yml`, `requirements-docs.txt`, `scripts/docs.{sh,bat}` deleted rather than rebuilt. `.agents/context/` remains the sole documentation. |
