# BUG-001 — `IEngineContext` docstring names a class that does not exist (`AppRunner`)

> **Closed 2026-08-23.**
>
> - **Req 1 — the mention was dropped, not renamed.** Confirmed against `kernel/app_runner.py`'s
>   actual constructor (`ApplicationRunner.__init__(self, app: App, input_port: IInputPort,
>   output_port: IOutputPort)`) — it takes no context at all, so listing it under "VALID usage of
>   IEngineContext" would be wrong even spelled correctly. The docstring now names the real,
>   closed set of context-holding orchestrators (`architecture.md`'s "IEngineContext — God Object
>   Prevention") and explicitly states `ApplicationRunner` is not one of them.
> - **Req 2 — done.** `grep -rn "AppRunner" sagittarius_engine/` returns nothing outside a stale
>   `.pyc` in `__pycache__` (irrelevant, not source).
> - **Req 3 — done.** `doc-code-sync.md:63`'s row is marked closed in place rather than deleted —
>   it stays as the historical example the rule file's own intro references.
> - **Req 4 — considered, decision recorded rather than left implicit: not extending the guard.**
>   The reason narrows the decision rather than closing it generally: `AppRunner` was not even
>   backtick-quoted in the source docstring, so a check modelled on
>   `tests/test_agents_docs_resolve.py` (which scans backtick-quoted tokens) would not have caught
>   this specific bug — it would need bare-word scanning across every Python docstring. That
>   checker's narrower, more constrained scope (`.agents/context/`) already needs a growing
>   `IGNORE_TOKENS` list to avoid false positives; the same approach across all of
>   `sagittarius_engine/`'s docstrings (33 files reference a backtick-quoted-looking class name
>   today) is a materially larger false-positive surface, for a bug class rated Low severity here.
>   Not worth building now. Revisit if a second live instance of this pattern is found.


**Reported date:** 2026-08-23
**Severity:** Low (documentation-level; no runtime impact)
**Status:** 🔴 Open

---

## 1. Symptom

`sagittarius_engine/interfaces/i_engine_context.py:30`, inside the docstring that defines where
`IEngineContext` may legitimately be used:

```python
    ✅ VALID usage of IEngineContext:
    - Inside IExtension.register(), boot(), shutdown() methods.
    - Inside IHostedService.start() and stop() methods.
    - Inside the Kernel's Bootstrap and AppRunner orchestrators.
```

**There is no `AppRunner` class anywhere in this repository.** The real orchestrator is
`ApplicationRunner`, defined in `sagittarius_engine/kernel/app_runner.py:13`.

Verified:

```
$ grep -rn "class AppRunner" sagittarius_engine/
(no results)

$ grep -n "^class" sagittarius_engine/kernel/app_runner.py
13:class ApplicationRunner:
```

## 2. Why this matters more than a typo

The two are **not** the same class with a shorter name. `.agents/rules/architecture.md:48-51`
already spells out the difference:

> There is no `AppRunner` class. `kernel/app_runner.py` defines **`ApplicationRunner`**, and it
> takes `App` + `IInputPort` + `IOutputPort` — it never receives a context at all. Do not add
> one; the ports *are* its boundary.

So the docstring does not merely misname a class — it states that a context-free orchestrator
receives `IEngineContext`, which is the exact opposite of the architectural rule the same
docstring exists to communicate. An AI session or developer reading this interface's own
docstring is told to do the thing `architecture.md` forbids.

## 3. Why it's still open — the part worth noting

This is **already recorded as a known finding** in `.agents/rules/doc-code-sync.md:63`:

| `interfaces/i_engine_context.py:30` docstring names `AppRunner` | No such class exists; real orchestrator is `ApplicationRunner`, different constructor entirely | The class was renamed/replaced without a grep for its old name in docstrings |

It was catalogued as an example *in the rule file whose entire purpose is preventing docs from
drifting from code* — and then never actually fixed. Found still present on 2026-08-23 during
the engine audit, when `architecture.md`'s (correct) correction was cross-checked against the
source it describes.

The existing staleness guard (`tests/test_agents_docs_resolve.py`) does not catch it: that test
scans `.agents/context/**/*.md`, not Python docstrings.

## 4. Fix

1. `i_engine_context.py:30` → `ApplicationRunner`. Consider dropping the mention entirely
   instead: `ApplicationRunner` does **not** receive a context (`architecture.md` is explicit),
   so listing it under "VALID usage of IEngineContext" is wrong regardless of the spelling.
   Confirm against `kernel/app_runner.py`'s actual constructor before choosing.
2. `grep -rn "AppRunner" sagittarius_engine/` and confirm no other source docstring carries it.
3. Update `doc-code-sync.md:63`'s row to mark the finding closed, so the rule file stops citing
   an open example as if it were historical.
4. **Consider extending the guard**: `tests/test_agents_docs_resolve.py` currently checks
   backtick-quoted names in `.agents/context/`. The same class of rot lives in Python
   docstrings, uncovered. Whether that's worth automating is a judgement call — record the
   decision either way rather than leaving it implicit.

## 5. Category

Documentation / Interfaces
