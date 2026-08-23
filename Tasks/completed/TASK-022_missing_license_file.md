# TASK-022: Package declares MIT but ships no LICENSE file

> **Closed 2026-08-23.** All four requirements done.
>
> - **Req 1** — `LICENSE` added at the repo root with the standard MIT text.
> - **Req 2 — the owner's decision, taken by the owner.** The copyright line is
>   `Copyright (c) 2026 AnhEmbedded Team`. The holder was confirmed by the user rather than
>   guessed, as this task insisted; it matches `pyproject.toml`'s own `authors` entry
>   (`{name = "AnhEmbedded Team", email = "Anh.Embedded@gmail.com"}`), so the package metadata
>   and the licence file now agree. The year is 2026 because every commit in this repository's
>   history is from 2026 (`git log --reverse --format=%ad`).
> - **Req 3 — verified, not assumed.** Built both artifacts and inspected them:
>   the wheel carries `sagittarius_engine-2.2.0.dist-info/licenses/LICENSE` and the sdist carries
>   `sagittarius_engine-2.2.0/LICENSE`. Modern setuptools did pick up the root file
>   automatically, but this repo has shipped wheels missing files it believed were included
>   (`TASK-024`, and the stale-asset defect found in `TASK-027`), so it was checked.
> - **Req 4** — `readme.md`'s License section is now a plain one-line link to `LICENSE`; the
>   warning block pointing at this task is gone.
>
> Locked in by `tests/test_license_file.py`: the file exists and contains the required MIT
> clauses, the copyright line carries no leftover placeholder, `pyproject.toml` still declares
> MIT (so a relicence cannot silently desync the two), and the built wheel actually ships the
> licence.

## Description

`pyproject.toml` declares the project MIT-licensed in two places:

```toml
license = {text = "MIT"}
...
"License :: OSI Approved :: MIT License",   # classifier
```

There is no `LICENSE` file at the repo root. `readme.md`'s Licence section linked to one until
2026-08-23, when the link was found dangling during EPIC-002D's doc audit and replaced with a
pointer to this task.

## Why it matters

The declaration is a claim; the file is the grant. Without the file:

- The published sdist/wheel carries an MIT classifier but no licence text, which is what
  downstream consumers' automated licence scanners actually read. Some will flag the package
  as unlicensed regardless of the metadata.
- GitHub does not display a licence for the repo, and `readme.md`'s installation section
  actively invites `pip install git+https://…` — so people are being asked to depend on code
  whose terms aren't stated anywhere in the tree.
- MIT requires the copyright notice and permission text be included in distributions. That is
  not currently possible, because the text does not exist.

## Requirements

1. Add a `LICENSE` file at the repo root with the standard MIT text.
2. **The copyright line needs a decision only the owner can make** — the holder's name and the
   year(s). This was deliberately not guessed when the task was filed. Fill in whatever is
   correct for this project.
3. Confirm the file is included in the built distribution (`python -m build`, then inspect the
   sdist/wheel — modern setuptools picks up a root `LICENSE` automatically, but verify rather
   than assume).
4. Restore `readme.md`'s Licence section to a plain one-line markdown link to the new
   `LICENSE` file, and delete the warning block pointing here.

## Priority

P2 — no functional impact, but it is a distribution-correctness problem on a package the
readme tells people to install, and it takes minutes to fix.

## Category

Packaging / Legal
