# TASK-027: Engine ships no `py.typed` — consumers get zero type information

## Description

`sagittarius_engine/` is fully annotated, and the project enforces strict typing on itself
(`.agents/context/lint.md`: *"Every function signature, argument, and return type MUST be
explicitly typed"*). None of that reaches consumers, because the package has no `py.typed`
marker file.

Under **PEP 561**, a type checker ignores inline annotations in an installed package unless the
package declares itself typed with a `py.typed` marker. Without it, every consumer sees
`sagittarius_engine` as untyped.

Confirmed: `find sagittarius_engine -name py.typed` returns nothing.

## This is already costing the main consumer

`Sagittarius_Elite_Warrior/pyproject.toml` carries an explicit workaround, and its comment
names the engine directly:

```toml
[[tool.mypy.overrides]]
# python-binance and sagittarius_engine ship no type stubs / py.typed marker — a third-party/engine gap,
# not our code's debt. Without this, mypy's "Skipping analyzing"
# resolution failure cascades into dependents in a way that silently shrinks how many files get fully checked.
module = ["binance", "binance.*", "sagittarius_engine", "sagittarius_engine.*"]
ignore_missing_imports = true
```

The consequence that comment describes is the important part: `ignore_missing_imports` does not
merely lose types at the boundary — the resolution failure **cascades into dependents**, so
files that import engine symbols get less thorough checking than their author believes. The
engine's missing marker is quietly degrading type safety in the app that depends on it.

## Requirements

1. Add an empty `sagittarius_engine/py.typed`.
2. Declare it in `pyproject.toml` so it ships in the wheel:
   ```toml
   [tool.setuptools.package-data]
   sagittarius_engine = [
       "py.typed",
       ...existing QML entries...
   ]
   ```
3. Build and verify the marker is actually present in the wheel (`python -m build`, then
   inspect). The existing `package-data` block is the only mechanism putting non-`.py` files in
   the distribution, and it was recently found to be missing the SDK templates — so verify
   rather than assume.
4. **Then remove the override in `Sagittarius_Elite_Warrior/pyproject.toml`** (keep the
   `binance` entry, drop the `sagittarius_engine` entries) and run its mypy. Expect new errors:
   they were always there, just unreported. Fixing them is the point.
5. Note that adding `py.typed` makes the engine's own type errors visible to consumers — worth
   sequencing after [TASK-021](TASK-021_ruff_config_shadowing.md)'s mypy cleanup, so consumers
   don't inherit a wave of engine-side noise on day one.

## Priority

P2 — cheap to fix, and it is currently degrading type checking in the primary consumer in a way
that is invisible from either side.

## Category

Packaging / Typing
