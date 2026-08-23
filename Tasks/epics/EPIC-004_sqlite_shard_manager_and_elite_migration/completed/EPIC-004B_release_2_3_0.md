# EPIC-004B — Release `2.3.0` and Install Into Elite

**Epic:** [EPIC-004](../README.md)
**Status:** ✅ Completed (2026-08-23)
**Category:** Packaging / Release
**Depends on:** [EPIC-004A](EPIC-004A_sqlite_shard_manager.md)

---

## 🎯 Objective

Get the new capability into `Sagittarius_Elite_Warrior`'s real environment, and establish
whether the upgrade **on its own** changes anything there — before any of that app's code is
touched. Without this checkpoint, a failure after migration could not be attributed to either
the upgrade or the migration.

## What was done

- `pyproject.toml` `2.2.0` → **`2.3.0`** (minor: new capability, no breaking change for any
  single-database consumer), `CHANGELOG.md` entry covering both EPIC-003 and EPIC-004.
- Built wheel + sdist, and **verified the wheel's contents** before installing —
  `sqlite_shard_manager.py`, `i_database_manager.py`, `database_manager.py` and `py.typed` all
  present. This check exists because `2.2.0` shipped a stale-wheel packaging defect that
  affected every wheel this repo had built to that point; a version number is not evidence.
- Installed into Elite's real venv (`--force-reinstall --no-deps`) and confirmed
  `importlib.metadata.version` → `2.3.0` with `SqliteShardManager` importable.
- Ran Elite's own full gate with the new engine and **its original code**.

## Result — the upgrade alone is clean

1776 passed / 50 sanity / `RESULT: PASS` — identical to the pre-upgrade baseline.

One methodological note kept deliberately: that gate run overlapped with the first edits to
Elite's source, which would normally invalidate it. It was confirmed valid from the log
itself — the run contains the **old** `test_database_manager_path_traversal`, and that test
passes only if the old module was the one imported (it monkeypatches a module-level
`_VALID_SYMBOL_REGEX` that the migrated version does not have). Old test present and passing
⇒ old code under test.
