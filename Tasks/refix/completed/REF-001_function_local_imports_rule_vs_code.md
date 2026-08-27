# REF-001: `code-rule.md` §45 ("never") vs. 32 function-local imports in the engine

- **Status**: ✅ Done 2026-08-27
- **Category**: Rules / Code Quality
- **Found while**: implementing `EPIC-007A`, reviewing the codebase's own local-import
  patterns before adding one of its own

---

## 1. The disagreement

`code-rule.md` §45 (as of `144dbc0`):

> **No Function-Local / Lazy Imports** … Never place `import ...` inside functions, methods,
> slots, test cases, or nested scopes (the only exception is `if TYPE_CHECKING:` guards at
> top level).

An AST walk of `sagittarius_engine/` found **32** function-local imports. Neither side gets
to be assumed right: a rule that says "never" and is broken 32 times might mean the code is
wrong, or it might mean the rule claimed more than was ever true.

## 2. Reconciliation

Each site was tested empirically, not judged by reading — hoist the import to module scope
(inserted after the docstring and any `__future__` import) and try `import <module>` fresh.

| Result | Count | What it means |
| :--- | :---: | :--- |
| Hoists cleanly, no stated reason | **12** | The rule was right; the code was wrong |
| Fails to hoist: optional dependency absent | **9** | The code was right; the rule was too absolute |
| Hoists cleanly, but the comment claims a cycle | **11** | Unproven either way — see §4 |

**32 = 12 + 9 + 11.**

### 2.1 The 12 fixed

Plain, unjustified local imports — `logging`, `warnings`, `typing.cast`,
`concurrent.futures.wait` — in modules that in several cases already imported the same name
at the top:

- `extensions/pyside_mvc/safety/ui_matrix_mixin.py` — `logging` (module had no top-level
  imports at all)
- `infrastructure/logging/tcp_log_viewer_handler.py` — `logging`, twice (already imported at
  line 2; the local import shadowed a name already available)
- `runtime/hosted/background_service.py` — `logging`
- `infrastructure/container/std_container.py` — `typing` (`typing.get_type_hints` now
  imported by name alongside the existing `Any, TypeVar, cast`)
- `kernel/app.py` — `warnings`, twice
- `kernel/extension_manager.py` — `typing.cast`, three times (one `TYPE_CHECKING` import
  already existed; widened to include `cast`)
- `infrastructure/config/config_manager.py` — `logging` (error-path only; the three
  `ConfigSource` subclass imports in this file are Category B, §2.2)
- `runtime/tasks/task_manager.py` — `concurrent.futures.wait` (module already imported
  `ThreadPoolExecutor` from the same package)

Verified: `pytest tests/` (minus the two Qt-dependent packages) — **930 passed**, identical
to the pre-change count; the change touches nothing behavioural.

### 2.2 The 9 kept, as Category A

An optional dependency, imported at its single point of failure. The wheel declares no
`[project] dependencies` at all (`pyproject.toml`); a module-scope import of any of these
makes the module unimportable in an install that legitimately lacks the package — which is
`EPIC-005` §2's **D7**, reproduced: *"the wheel is zero-dependency by design, but
`tools/audit_dashboard/main.py` imports `PySide6.QtWidgets` at module level … dies on
`ModuleNotFoundError` before reaching any of its own code."*

`websockets` (×3), `opentelemetry.*` (×4), `sqlalchemy` (×1), `dotenv` (×1). Each already
carried a comment to this effect before this refix — `cli.py:75`'s is the clearest:

> Imported here, not at module level, for the same reason `TraceServer._serve()` imports
> `websockets.asyncio.server` inside itself: this is the one place an install without the
> transport's runtime dependency would fail, and it should fail clearly at this exact line
> rather than somewhere unrelated.

### 2.3 The 11 kept, as Category B — and *why* "kept" is not "endorsed"

Intra-engine imports whose comment claims breaking an import cycle: `kernel/context.py` (×6,
importing the runtime managers it constructs), `infrastructure/config/config_manager.py`'s
three `ConfigSource` subclass imports, `kernel/module_auto_discovery.py` importing
`module_loader`, `extensions/diagnostics/runtime.py` importing `event_registry`.

**Every one hoisted cleanly in isolation.** That is recorded honestly rather than treated as
proof: hoisting one import and re-running `import <module>` shows the module has no cycle
*when nothing else has already run*. It cannot show there is no cycle under every import
order a real application produces — module-scope side effects, a consumer importing these in
an unusual sequence, or a cycle that only manifests through a third module not exercised by
this check. `design-discipline.md`'s own worked example is exactly this trap: *"'It works
now' is not a diagnosis. A fix whose stated cause is wrong is worse than no fix."* Declaring
these cycle-free from a single-import probe would be that mistake with extra steps.

So they are **sanctioned, not hoisted** — kept local, but only inside a named, tested
allowlist, which is a stricter position than either "trust the comment" or "the probe passed,
hoist it." A follow-up that runs each candidate through the actual import orders the test
suite and the sample app produce — not just a fresh interpreter — can retire rows from
`SANCTIONED_LOCAL_IMPORTS` on real evidence. Filed as `TASK-041` (see §5).

## 3. The rule, amended

`code-rule.md` §45 now states two bounded exceptions instead of "never", each requiring a
comment at the import site naming which exception applies:

1. An optional dependency, at its single point of failure.
2. Breaking a measured import cycle — with this refix's finding recorded inline: eleven such
   sites currently hoist in isolation, which does not disprove an order-dependent cycle but
   does mean each is a candidate for removal rather than a precedent to copy.

`if TYPE_CHECKING:` guards remain unrestricted, unchanged from before.

## 4. What enforces it

`tests/test_architecture.py`:

- `SANCTIONED_LOCAL_IMPORTS` — the 20 rows (9 Category A + 11 Category B), each a
  `(path, module)` pair. Same shape as `import_boundary.SANCTIONED_DEEP_IMPORTS`, which
  `design-discipline.md` names as the reference case for debt that is *"named, justified and
  bounded so it cannot spread."*
- `find_function_local_imports()` — an AST walk, not a grep, so an import nested in a `try`
  or a closure is found the same as one directly in the function body.
- `test_no_unsanctioned_function_local_imports()` — fails on any site outside the allowlist.
  A new function-local import now fails a test instead of merging silently, which is how
  these 32 accumulated under a rule that said "never."
- `test_every_sanctioned_local_import_still_exists()` — fails if the allowlist keeps a row
  whose site was fixed. An allowlist that only grows stops being a bound.

## 5. Follow-up filed, not folded in here

**`TASK-041`** (filed on `Tasks/README.md`'s backlog): re-probe the 11 Category B sites
against the import orders the real test suite and `examples/student_management` produce,
not a fresh interpreter — and hoist whichever survive. Left as its own task because it needs
a different method than this refix (multi-order import tracing, not single-shot), and
bundling it here would have let "the guard exists" stand in for "the cycle claim was
verified," which is the exact gap §2.3 just refused to paper over.

## 6. Verified

| Gate | Result |
| :--- | :--- |
| `pytest tests/test_architecture.py` | **13 passed** |
| `pytest tests/` (minus `pyside_mvc`, `ui_state` — no PySide6 here) | **930 passed**, unchanged from before the hoists |
| `pytest tests/test_agents_docs_resolve.py` | 1 passed; 1 pre-existing shallow-clone failure, unrelated (`git show` on an object absent from a shallow `.git/shallow` checkout) |
| `ruff check` / `ruff format --check` (CI scope) | clean |
| `mypy` (CI scope) | 1 pre-existing error (`thread_affinity.py:124`, PySide6 absent — named as such in `ci.yml`) |

## Run it

```bash
.venv/bin/python -m pytest tests/test_architecture.py -k local_import -v
```
