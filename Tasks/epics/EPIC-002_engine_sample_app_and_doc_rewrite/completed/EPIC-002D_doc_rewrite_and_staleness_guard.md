# EPIC-002D — Doc Rewrite & Staleness Guard

**Epic:** [EPIC-002 — Engine Sample App & Doc Rewrite](../README.md)
**Status:** ✅ Completed 2026-08-23
**Category:** Documentation / Developer Experience
**Priority:** P1
**Depends on:** EPIC-002C (rewrites from the audit, not from memory)

---

## 🎯 Summary & Objectives

Rewrite `.agents/context/` using `AUDIT_REPORT.md` as the source of truth, and add a
mechanism so it cannot silently rot the way it just did (one commit, 2026-08-02, wrong by
2026-08-23 with nobody noticing for three weeks).

1. **Restructure or fully delete-and-rewrite `.agents/context/` — your call, decided per
   file, not a fixed policy.** User's explicit instruction: *"co the tai cau truc lai doc,
   hoac xoa het viet lai"* (can restructure, or delete everything and rewrite). A file that's
   mostly right (e.g. `testing.md`, unaudited so far — verify) may only need a factual patch;
   a file `AUDIT_REPORT.md` shows is structurally wrong (`repository.md`'s wrong repo name,
   `modules.md`'s `IModule`-as-the-model framing) should be deleted and rewritten from zero
   rather than patched into something that still carries its original, wrong shape.
2. **Separate what rots from what doesn't**, per the pattern already validated by this
   session's audit of `architecture.md`:
   - Facts fully derivable from code (directory trees, class lists, method signatures) —
     minimize hand-written duplication; where a list must exist, keep it exhaustive and
     dated, not illustrative.
   - Decisions and their reasons (why `IExtension` replaced `IModule`, why tokens are
     engine-owned) — these don't go stale the same way; keep them, and keep them adjacent to
     the evidence that grounds them.
   - Traps (lifecycle override/call split, `QT_QPA_PLATFORM` offscreen default,
     `QQuickWidget.errors()` blindness) — highest value per byte; pull these from
     `AUDIT_REPORT.md` and `design-discipline.md`/`surprising-findings.md` almost verbatim.
3. **Point every context doc at the sample app** where it illustrates a real pattern — the
   sample is the reference now (see epic README's framing), and a doc describing "how a
   consumer wires an extension" should cite the sample's actual file rather than an invented
   snippet, per this repo's own `design-discipline.md` root-cause standard.
4. **Fix the 4 dangling references** to the deleted old `examples/student_management/`:
   `readme.md:131`, `.agents/context/examples.md`, `.agents/context/modules.md`,
   `.agents/skills/module_discover.md` — point them at the new sample.
5. **Add a staleness-detection test.** One test, scanning `.agents/` for backtick-quoted
   `ClassName`/`module.path`/`dir/path` tokens and asserting each resolves against the real
   tree (via `ast`/`importlib`/`pathlib`, whichever is cheapest to keep correct). This is what
   would have caught `AppRunner`, `Sagittarius_ForkBoy`, and `extensions/sqlalchemy` on day
   one instead of three weeks later. False positives (prose that happens to look like a path)
   are an acceptable cost — an explicit ignore-list is fine, an unchecked doc is not.
6. Register this epic's outcome in `Tasks/README.md`'s epic table and `Tasks/epics/README.md`
   per the standing convention (this epic itself, once EPIC-002A starts, should already be
   listed — verify it still is by the time this subtask runs).

## 📐 Design Constraints

- Do not soften a doc's claim to make it "not wrong anymore" without checking whether the
  underlying rule/behavior itself needs a decision (`design-discipline.md`'s 3-step: cause →
  check against written rules → then write). A doc rewrite is still a design-discipline
  situation, not a free pass to reword around a real problem.
- Keep `ui-architecture.md` and `design-discipline.md` as the reference for *how* a rule file
  earns trust (dense, example-grounded, dated evidence) — this subtask's output should read
  at the same level, not regress to the old `context/` style.

## 🧪 Verification & Test Coverage

- The staleness-detection test exists, passes against the rewritten docs, and is proven to
  actually catch drift (write it against the *old*, since-deleted `repository.md` content
  first — from git history — confirm it would have failed, then confirm it passes clean).
- Every claim in the rewritten `.agents/context/*.md` traces to either the sample app, the
  audit report, or a direct code citation — no claim restored from the old files without
  re-verification.
- `.agents/ONBOARDING.md`'s context/rule routing tables still resolve every listed file
  (`PLAYBOOK.md`/`manifest.yml` were retired 2026-08-23 in favor of this file — see its own
  §5 "known duplication" note, which this subtask resolves).

---

## ✅ Outcome — completed 2026-08-23

### Per-file disposition of `.agents/context/` (objective 1)

Decided per file, as the objective allowed, not by blanket policy.

| Disposition | Files |
| :--- | :--- |
| **Deleted and rewritten from zero** | `repository.md`, `modules.md`, `examples.md`, `testing.md`, `dependencies.md`, `configuration.md`, `api.md` |
| **Patched** (structurally sound, factually wrong in places) | `project.md`, `glossary.md`, `troubleshooting.md`, `architectures/architecture.md`, `runtime.md`, `build.md`, `lint.md` |
| **Consolidated and deleted** | `deployment.md` → merged into `rules/deployment.md` (a 3-line stub that now carries the real content); `documentation.md` → deleted outright, a pure duplicate of `rules/documentation.md` + `rules/doc-code-sync.md` |

Net: 16 files → 14. `.agents/ONBOARDING.md` §4's routing table was updated to match, including
its stale "16 files" count and its two now-dangling rows.

### Errors found and fixed while rewriting

Beyond what `AUDIT_REPORT.md` had already catalogued, the rewrite surfaced these — each
verified against real code, not inferred:

| Doc | Claim | Reality |
| :--- | :--- | :--- |
| `repository.md` | `docs/` holds "~51 files" of tutorials and API reference | **`docs/` does not exist.** Deleted in `a338d42`, never rebuilt (`git ls-tree -r HEAD` → 0 files). The "~51" was never verified against the tree. |
| `readme.md` | Documentation section links 7 subsections under `docs/` | All 7 dangling. `mkdocs.yml`'s `docs_dir: docs` means `mkdocs serve` fails outright. |
| `readme.md` | Examples table lists 5 example apps | 4 of them (`desktop/`, `worker/`, `trading_bot/`, `websocket/`) never existed. Rows removed. |
| `architectures/architecture.md` | audit_dashboard uses `IConnector` and `ReceiveAuditUseCase` | Real names are `IRealtimeConnector` and `StartRealtimeListenerCommand`. Both were plausible-sounding guesses. |
| `glossary.md` | Domain event example `StudentAddedEvent` | Real events are `StudentEnrolled` / `StudentUpdated` / `StudentRemoved`. |
| `runtime.md` | `TerminalMenu` as a `BackgroundService` example | No such class anywhere in the repo. |
| `build.md` | Packaging is `pyproject.toml` + `setup.py` | No `setup.py` exists. |
| `build.md` | 6 CI jobs | 7. `benchmark` was omitted — and is itself broken (below). |
| `lint.md` | Ruff config lives in `pyproject.toml` | A root `ruff.toml` **shadows** it entirely; the `extend-select` everyone assumes is active is dead config. |
| `skills/module_discover.md` | Write module docs to `docs/Modules/` | Directory deleted in `a338d42`. Retargeted to `.agents/context/modules/`. |

### Real engine gaps found → filed as tasks (not just described)

Per the standing rule that a real gap gets a `TASK-XXX` immediately:

- **[TASK-020](../../../backlog/TASK-020_ci_benchmark_job_stale_path.md)** — CI's `benchmark`
  job runs `tests/benchmark_runtime.py`, moved to `tests/runtime/` in `843137a`. It has errored
  ever since, invisibly, because the job sets `continue-on-error: true`. No benchmark has run
  in CI since that reorganization.
- **[TASK-021](../../../backlog/TASK-021_ruff_config_shadowing.md)** — `ruff.toml` shadows
  `pyproject.toml`'s `[tool.ruff]`; the intended rule set has never run. Also captures local
  toolchain drift from CI pins (local ruff 0.16.4 / mypy 2.3.1 vs pinned 0.15.20 / 2.1.0).
- **[TASK-022](../../../backlog/TASK-022_missing_license_file.md)** — `pyproject.toml` declares
  MIT, no `LICENSE` file exists, and `readme.md` linked to it.

### Staleness guard (objective 5)

`tests/test_agents_docs_resolve.py`, two tests, both passing.

Design, and its deliberate limits — stated here because a guard that overstates its reach is
worse than none:

- Scans backtick-quoted tokens in `.agents/context/**/*.md` and classifies each into one of
  four shapes (path, dotted module, bare class name, bare package name), then resolves it
  against the real tree, the real `requirements*.txt`, or a real `grep` for `class X`.
- **Scoped to `context/` only.** `rules/`, `skills/`, and `workflows/` are excluded by design:
  they backtick QML vocabulary (`Rectangle`, `busy`), generic Clean Architecture shapes
  (`src/domain/`), and paths in a *different repo* (`Sagittarius_Elite_Warrior`). Checking them
  produced ~80 findings, none real. Precision was chosen over reach.
- **`IGNORE_TOKENS` is an explicit, commented allow-list**, including a category for names a
  doc quotes *because they're wrong* (`IConnector`, `TerminalMenu`) — deleting those sentences
  would destroy the traceability `doc-code-sync.md` requires.
- Verified against real drift, as the objective demanded: the second test runs the checker
  against the pre-rewrite `repository.md` recovered from `git show 0bd461b:` and asserts it
  flags `Sagittarius_ForkBoy`.
- **What it cannot catch**, documented in the test's own docstring: the original
  `extensions/sqlalchemy` bug is now out of reach. `sqlalchemy` is a real pip dependency, so a
  word-existence check can't distinguish "real package, wrongly implied to be a local
  subpackage" from "real package, correctly named." Making dependency names resolve was
  necessary to stop `dependencies.md` flooding with false positives. That trade was taken
  knowingly and the assertion was rewritten to claim only what the mechanism actually proves,
  rather than left asserting something it no longer does.

### Verification

- `pytest -q` — **594 passed, 5 skipped**, no failures.
- `ruff check` + `mypy` clean on both touched Python files (`tests/test_agents_docs_resolve.py`,
  `examples/student_management/infrastructure/persistence/extension.py`). The 308 ruff and 29
  mypy findings elsewhere are pre-existing, all in `sagittarius_engine/` — untouched by this
  subtask, and now tracked under TASK-021.
- Link scan across all 73 markdown files under `.agents/`, `Tasks/`, and `readme.md`: 5 broken
  relative links found, 4 fixed (`EPIC-001A` moved to `completed/`, `test_runtime.py` moved to
  `tests/runtime/`, `TASK-015` moved to `completed/`, `TASK-009`'s source deleted in `b1ffca8`
  and now cited with its recovery command), 1 escalated to TASK-022 (`LICENSE`).
- `StudentManagementExtension.dependencies` declared as `ClassVar[list[str]]`; its docstring,
  which still claimed ordering was non-declarative, was corrected to match.
