# BUG-002 — `mkdocs.yml` builds from a `docs/` tree that no longer exists

**Reported date:** 2026-08-23
**Severity:** Medium (documented workflow is broken; no runtime impact on the shipped package)
**Status:** 🔴 Open

---

## 1. Symptom

`mkdocs.yml:4` declares:

```yaml
docs_dir: docs
```

There is no `docs/` directory in this repository. It was deleted whole — 53 files, 6070
lines — in commit `a338d42` ("Remove outdated tutorials and examples for Sagittarius Engine"),
2026-08-23, and never rebuilt.

Verified:

```
$ git ls-tree -r HEAD --name-only | grep -c "^docs/"
0

$ find . -type d -name docs -not -path "./.venv/*" -not -path "./.git/*"
./examples/student_management/docs      # a different, unrelated tree — the sample app's own design notes
```

Three artefacts are left dangling by that deletion:

| Artefact | State |
| :--- | :--- |
| `mkdocs.yml` | `docs_dir: docs` + a full `nav:` tree, all pointing at deleted files |
| `requirements-docs.txt` | Still present; installs a doc toolchain with nothing to build |
| `scripts/docs.sh` / `scripts/docs.bat` | Wrapper scripts for the same dead build |

## 2. Reproduction

Not directly reproducible in this environment — `mkdocs` is not installed in `.venv`
(`No module named mkdocs`), so I could not execute the failing build and capture its output.
What *is* verified is the precondition: `docs_dir` names a directory that provably does not
exist in the tree, and mkdocs cannot build from a missing source directory. Recording this
honestly rather than claiming a failure I did not observe.

To confirm when convenient:

```bash
pip install -r requirements-docs.txt
mkdocs build --strict
```

## 3. Why it's filed as a bug rather than left alone

`readme.md`'s Documentation section previously instructed readers to run `mkdocs serve`. That
instruction was corrected on 2026-08-23 (it now states plainly that the tree is gone and points
at `.agents/` instead), so the user-facing lie is already fixed — but the **config, the
requirements file, and the two wrapper scripts were left in place**, which is the actual
inconsistent state: a repo that carries a doc-build toolchain for a doc tree it deleted.

`.agents/context/repository.md` documents the situation accurately today, so this bug is not
about anyone being misinformed — it is about the leftovers still being there.

## 4. Fix — needs a decision, not just a deletion

Two coherent end states; pick one deliberately:

- **A — drop the doc site.** Delete `mkdocs.yml`, `requirements-docs.txt`, `scripts/docs.sh`,
  `scripts/docs.bat`. `.agents/` becomes the only documentation, which is what
  `readme.md` already tells people. Simplest, and matches how the repo currently actually works.
- **B — rebuild the doc site.** Restore or rewrite `docs/`, then fix `mkdocs.yml`'s `nav:` to
  match what actually exists. Substantially more work, and worth doing only if there is a real
  intent to publish a public doc site (see `TASK-022` — the package is also currently missing a
  `LICENSE`, so public-readiness is an open question generally).

Whichever is chosen, update `.agents/context/repository.md`'s `docs/` row and `readme.md`'s
Documentation section in the same change (`rules/doc-code-sync.md`).

## 5. Category

Build / Documentation

## 6. Related

- `TASK-022` — missing `LICENSE`; same underlying question of whether this package is meant to
  be publicly consumable.
