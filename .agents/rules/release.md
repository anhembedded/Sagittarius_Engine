---
name: Release
description: How to cut a release — version choice, changelog, clean build, wheel verification, tagging. Load for any task that bumps the version or publishes a version tag.
trigger: model_decision
---

# Rules: Release

> Context: this engine is consumed as `pip install git+https://github.com/anhembedded/Sagittarius-Engine.git`
> (`install-rule.md`). With that install method **a tag is the release** — a consumer pins with
> `@v2.1.0` and must get byte-identical code forever. Every rule below exists because the
> corresponding step was skipped at least once, and the evidence is cited inline.

---

## 0. Never release without an explicit instruction

`git commit`, `git tag`, and `git push` all require a direct order from the user for that
action, in that message (`code-rule.md` §9). Cutting a release is the *most* outward-facing
thing in this repo. Prepare everything, show it, and wait.

## 1. Most tasks are not releases

**Finishing a task is not a reason to cut a version.** Most work lands on `main` with no version
bump, no changelog entry, and no tag. Releases are deliberate, batched, and comparatively rare —
they are the user's call, not a step in a task's definition of done.

> **Why:** stated directly by the user on 2026-08-23 ("ko phai task nao cung release version")
> after a session bumped and tagged a version for each task it finished in sequence.

If work plausibly warrants a release, finish the task, say why, and let the user decide.

## 2. Version scheme: `a.b.c` — this is NOT semver

Do not apply semver reasoning here. Under semver the deciding question is "does this break
compatibility?" Under **this repo's scheme the deciding question is what *kind* of thing
changed**:

| Component | Bump when |
| :--- | :--- |
| **`a`** | a **feature** changes |
| **`b`** | the **published API** changes |
| **`c`** | the change is **only a bug fix** |

When more than one applies, the leftmost (most significant) one that changed wins. A large new
feature that breaks nothing still bumps `a`; a purely additive published-API change bumps `b`
rather than being argued about in compatibility terms. Do not describe a bump as "minor" or
"major" in the semver sense in commit messages or `CHANGELOG.md` — classify by these three.

For deciding what counts as the **published API**, this repo has an explicit, testable answer:
`tests/test_architecture.py::test_public_api_exports` pins `sagittarius_engine.__all__`. A change
to a name outside that set is still worth calling out, but it is not automatically a `b` bump.

Version lives in exactly one place: `version` in `pyproject.toml`. There is no `__version__` in
the package — verified 2026-08-23; if that changes, both must move together.

## 3. A `requires-python` change must land with a matching CI matrix entry, in the same change

`pyproject.toml`'s `requires-python` and the classifiers next to it are a support **claim**.
`.github/workflows/ci.yml`'s test matrix is what actually backs that claim with evidence. They
must move together.

> **Why:** `TASK-023`. `requires-python` once declared `">=3.12"` while the matrix only ever ran
> `3.14-dev`. That gap hid a real bug for as long as it existed: `runtime/tasks/task_manager.py`
> annotated a method with a name (`ITaskHandle`) it never imported. Python 3.14's deferred
> annotation evaluation (PEP 649) made this invisible — the module imported fine. Python 3.12/13
> evaluate annotations eagerly at `def` time, so the same code raised `NameError` on import,
> and `app.boot()` imports this module, meaning the engine's single most fundamental call almost
> certainly failed outright on two of the three versions the package claimed to support. Nobody
> could have caught it locally either, because CI is where the untested versions would have run.
>
> Resolved by narrowing the claim to `>=3.14` rather than widening the matrix, since 3.14 was
> confirmed to be the real target. If the floor is ever lowered again: add the matrix entry
> **first**, in the same PR as the `pyproject.toml` change — not as a follow-up — and run
> `tests/test_all_modules_importable.py` (it forces `typing.get_type_hints()` on every public
> interface, which is what actually would have caught `ITaskHandle` on day one) against the new
> minimum version before merging.

## 4. Build the changelog from the diff, not from memory

Determine the change set with `git diff <last-tag>..HEAD` — **not** from what you remember doing
this session.

> **Why:** the first `2.0.0` changelog entry was written from one session's commits and omitted
> the single largest breaking change in the release (the `QmlShared` → `Sagittarius.UI` QML
> module rename). It was caught only by installing the result into the consuming app, whose suite
> went from green to **69 failures**.

## 5. Always build clean — `build/` is not pruned

**Delete `build/` and `dist/` before every build.**

```bash
rm -rf build dist
python -m build --wheel --outdir dist
```

> **Why — measured 2026-08-23, this is not hypothetical.** `setuptools` copies `build/lib/` into
> the wheel wholesale. `package-data` controls what is copied *into* `build/lib` during
> `build_py`; it does **not** remove files already sitting there from an earlier build. A wheel
> built without cleaning shipped **9 stale assets** — `BaseCard.qml`, `LogPanel.qml`,
> `qmldir`, and six more under `extensions/pyside_mvc/QmlShared/` — none of which exist in the
> source tree, all left over from before the `2.0.0` QML rename that explicitly removed them.
> Cleaning first dropped it to **0**. `build/` is gitignored, so this is invisible to
> `git status` and survives indefinitely.
>
> Consequence if skipped: the wheel is not reproducible from source, and it re-registers a QML
> module a release claimed to delete.

## 6. Verify the wheel's contents — do not assume `package-data` worked

That block is the only mechanism putting non-`.py` files in the distribution, and it has been
wrong before (it omitted the SDK templates, so a pip-installed engine could not scaffold at all
— `TASK-024`).

```python
import zipfile, glob
names = zipfile.ZipFile(glob.glob('dist/*.whl')[0]).namelist()
assert 'sagittarius_engine/py.typed' in names          # PEP 561 marker
assert not [n for n in names if 'QmlShared' in n and not n.endswith('.py')]   # no stale assets
```

Check at minimum: `py.typed` present, expected `.qml`/`qmldir` present, **no** path in the wheel
that is absent from the source tree.

## 7. Run the real gate, and report its result honestly

`pwsh ./scripts/ci-local.ps1`, then read the printed `===CI_LOCAL_RESULT===` block and open
`LOG_FILE` — never judge from scrollback (`ONBOARDING.md` §1a).

A release may ship with a **known, pre-existing** failure, but the changelog must say so, name
the tracking task, and state that it predates the release. Never describe a red gate as green,
and never claim an acceptance criterion is met when it is not (`design-discipline.md`).

## 8. Write the changelog entry

`CHANGELOG.md`, newest first, `## [X.Y.Z] — YYYY-MM-DD`. Sections used here: `⚠️ Breaking`,
`Added`, `Fixed`, `Changed — behaviour`, `Known issues`, and an `Upgrade checklist` for anything
consumers must act on.

Every claim must be checkable — cite the file, the task ID, or the measurement. If a number is
quoted (error counts, test counts), state the exact command that produced it; two tasks quoted
different mypy baselines on 2026-08-23 (27 vs the gate's actual 24) because neither recorded its
invocation.

## 9. Tag — annotated, and pushed explicitly

```bash
git tag -a vX.Y.Z -m "<summary>"
git push origin vX.Y.Z
```

- **Annotated (`-a`), never lightweight** — a release tag carries authorship and a message.
- **`git push` does NOT push tags.** Verified 2026-08-23: the `2.1.0` release commit reached
  `origin/main` while `v2.1.0` stayed local, leaving a released version nobody could pin. Push
  the tag by name and confirm with `git ls-remote --tags origin`.
- **Tag only a commit that is an ancestor of `origin/main`.** Sync first; a tag on an unmerged
  local commit can end up off the mainline entirely.

A **tag** is the release. A **release branch** (`release/X.Y.x`) is a different, optional tool —
a maintenance line for backporting a `X.Y.1` fix once `main` has moved on. Do not create one
unless something actually needs backporting.

## 10. Keep tags and the changelog in agreement

Every version with a `CHANGELOG.md` entry should have a tag, and vice versa. As of 2026-08-23
this repo does **not** satisfy that — `1.5.0` and `2.0.0` are documented releases with no tag,
so `v1.0.0` is followed directly by `v2.1.0`. Do not widen that gap; backfill deliberately if
asked.

## 11. This repo is sometimes worked by two sessions at once

A concurrent local session may push to the same remote mid-release. Before tagging: `git fetch`,
confirm the release commit is on `origin/main`, and re-run the gate on the merged tree — not on
the tree as it looked before syncing.
