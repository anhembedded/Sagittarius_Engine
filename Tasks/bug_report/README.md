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
| 🔴 **Open** | 4 |
| ✅ **Fixed** | 7 |
| 📈 **Total** | **11** |

`BUG-004` and `BUG-005` were found on 2026-08-24 during a cross-repo audit run for
`Sagittarius_Elite_Warrior`'s `EPIC-007`/`EPIC-008`. Both are defects in **this** repo, so
they are tracked, fixed and committed here — the app repo's epics only reference them
(`.agents/ONBOARDING.md` §8). Both closed 2026-08-25.

The three fixed ones were found on 2026-08-23 during the engine audit that followed `EPIC-002`. Defects
found in the *same* audit that already had a fix applied were tracked as tasks instead, because
they were closed in the same session — see `TASK-024`, `TASK-025`, and the `ITaskHandle` import
bug fixed in commit `568d3bb`. Future defects should come here first.

### ⚠️ Numbering is not automatic — two sessions collided here

On 2026-08-25 two sessions each took "the next number" at the same time and
**both `BUG-008` and `BUG-009` were used twice**, for four different defects.
Worse, both `BUG-008`s were cited from source: `style.py` meant the QSS
cascade, `bootstrap.py` meant the post-boot stranding.

Resolved by renumbering the two that were still **open** (they had to be added
to this board anyway) to `BUG-010`/`BUG-011`, and updating every reference —
`bootstrap.py`, `EPIC-006C`, that epic's README, and `TASK-040`. The two fixed
ones keep `BUG-008`/`BUG-009`, which are already cited from regression-test
docstrings and the app repo.

`tests/test_bug_board_is_consistent.py` now blocks a repeat: no number may be
used twice, every file must have a row here, and every row must point at a file
that exists.

Elite's own `BUG-008`/`BUG-009` are unrelated and fine — the two boards are
deliberately independent (see the top of this file).

---

## 🔴 Open

| ID | Title | Severity | Reported | Note |
| :--- | :--- | :---: | :---: | :--- |
| **[BUG-011](incomplete/BUG-011_ci_local_gate_test_crashes_on_windows_stdout_none.md)** | `test_ci_local_gate_missing_tool` crashes on Windows: `result.stdout` is `None` despite `capture_output=True` | Medium | 2026-08-25 | A `TASK-028` regression guard that cannot report on the one platform it guards. Filed by `TASK-040`, once the `test` job actually started running again. **Renumbered from `BUG-009` on 2026-08-25** — see the numbering note below. |
| **[BUG-010](incomplete/BUG-010_post_boot_registration_strands_an_extension_silently.md)** | Registering an extension after boot strands it silently, and the engine still reports `ready` | Medium | 2026-08-25 | `ExtensionManager.register()` defers an extension whose dependencies are unmet and never raises, so a plugin added to a running engine sits uninitialised while lifecycle still reads `ready`. Found by `EPIC-006C`. **Renumbered from `BUG-008` on 2026-08-25** — see the numbering note below. |
| **[BUG-007](incomplete/BUG-007_resilient_bus_drops_a_subscription_on_name_collision.md)** | `ResilientEventBus.on()` silently drops a subscription when two event classes share a `__name__` | Medium | 2026-08-25 | Keys `_wrapper_map` by `__name__` while the rest of the package keys by `event_name`/`__qualname__`; the colliding second `on()` early-returns and the handler never fires. Reproduced. Found while fixing `EPIC-008C`, filed separately rather than fixed inline. |
| **[BUG-006](incomplete/BUG-006_qml_warning_tests_are_order_dependent.md)** | The two "no QML runtime warnings" tests assert on the whole Qt message stream, so a once-per-process platform warning makes them order-dependent | Medium | 2026-08-25 | gallery-first → gallery fails; roster-first → both pass. Same code, opposite results. On Windows the contaminant is a `QFontDatabase` platform warning; **on Linux it is 32 `RosterScreen.qml` teardown `TypeError`s** that normally land after pytest's summary line and move inside the test when unrelated test files shift timing (found 2026-08-25 during `EPIC-007A`). Neither is a QML binding error the test was written to catch. **Đo 2026-08-25: không chỉ phụ thuộc thứ tự mà còn KHÔNG TẤT ĐỊNH** — cùng commit, cùng lệnh, 3 lần chạy cho 1 đỏ / 2 xanh. Suite xanh không còn là bằng chứng cho test này. |

---

## ✅ Fixed

| ID | Title | Severity | Reported | Note |
| :--- | :--- | :---: | :---: | :--- |
| **[BUG-009](completed/BUG-009_statcard_badge_tone_stopped_rendering_after_bug008.md)** | `StatCard.set_badge()`'s tone stopped rendering once `BUG-008` scoped the role QSS | Medium | 2026-08-25 | Fixed 2026-08-25: the append produced a bare property after a closing brace, which Qt discards (it even logs "Could not parse stylesheet"). Delegates to `Badge.set_tone()` now. **The existing test passed the whole time** — it asserted the stylesheet string *ended* in the tone token, and the broken output still did. Rewritten to assert structure (nothing may dangle after the last `}`), confirmed red before / green after, and verified by rendering pixels, not just the string. |
| **[BUG-008](completed/BUG-008_apply_role_qss_cascades_into_every_child.md)** | `apply_role()` wrote unscoped QSS for `SURFACE`/`SECTION_LABEL`/`CAPTION`/`TABLE_HEADER`/`CHECKBOX`/`FIELD`, so a `Card`/`Panel` restyled every child widget that had no stylesheet of its own | High | 2026-08-25 | Fixed 2026-08-25: `apply_role()` now wraps unscoped role QSS in a type selector built from the widget's own runtime class before `setStyleSheet()`; already-scoped roles pass through unchanged. Also fixed a second defect it exposed — `Badge.set_tone()` string-concatenated a bare property that would have dangled after the new scoped block. 2 new regression tests in `test_surface.py`, 1 existing assertion in `test_labels.py` rewritten. Full suite: 1262 passed, 0 failed. |
| **[BUG-004](completed/BUG-004_overlay_names_nonexistent_subclasses.md)** | `Overlay`'s docstring and `TypeError` message name `ConfirmOverlay`/`PickerOverlay`, which exist nowhere | Medium | 2026-08-24 | Fixed 2026-08-25: both written, one file per class under `widgets/overlays/`, exported from `__all__`. Closed by writing them rather than by dropping the mention — 9 real consumers were waiting in the app repo. The regression test resolves the names *out of the message itself*, so rewording cannot reintroduce a phantom. 1004 passed, coverage 89.46%. |
| **[BUG-005](completed/BUG-005_baseevent_inheritance_is_inert_for_dataclasses.md)** | Inheriting `BaseEvent` gave a `@dataclass` subclass nothing — `event_id`, `occurred_on`, `to_dict()` all raised `AttributeError` | High | 2026-08-24 | Fixed 2026-08-25: `BaseEvent` is now a `@dataclass` with `kw_only` metadata fields backed by concrete properties (a public dataclass field with the same name as the inherited abstract property re-triggers `abc.update_abstractmethods()` and breaks instantiation — avoided). `event_name` defaults via `__init_subclass__`. 8 new regression tests, all 3 existing engine consumers unaffected. |
| **[BUG-003](completed/BUG-003_get_logger_annotation_contradicts_iengincontext_contract.md)** | `_get_logger()` declared `ILogger \| None` against a contract that guarantees non-None | Low | 2026-08-23 | Fixed 2026-08-23: 4 mypy errors resolved (27→23). Also removed 6 dead `if logger:` guards in `bootstrap.py`, by explicit user decision. 757 passed, 0 failed. |
| **[BUG-001](completed/BUG-001_phantom_apprunner_in_iengincontext_docstring.md)** | `IEngineContext` docstring names a nonexistent `AppRunner` class | Low | 2026-08-23 | Fixed 2026-08-23: mention dropped (not renamed) — `ApplicationRunner` takes no context at all, per its real constructor. `doc-code-sync.md:63`'s row marked closed in place. |
| **[BUG-002](completed/BUG-002_mkdocs_config_points_at_deleted_docs_tree.md)** | `mkdocs.yml` builds from a `docs/` tree deleted in `a338d42` | Medium | 2026-08-23 | Fixed 2026-08-23: Option A chosen — `mkdocs.yml`, `requirements-docs.txt`, `scripts/docs.{sh,bat}` deleted rather than rebuilt. `.agents/context/` remains the sole documentation. |
