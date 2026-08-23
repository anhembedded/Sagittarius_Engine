# Process a Task

## Working rules

- Continue working until the task is actually complete; do not stop at partial progress reports.
- A task is only complete when the verification scripts for the touched scope pass. In this repository, the default completion gates are `scripts/ci-local.ps1` (moved from `pre_commit.ps1` at the repo root, 2026-08-23 — see `TASK-030`) and `Sagittarius_Elite_Warrior/scripts/run-ui.ps1` for the app UI path.
- Prefer autonomous execution over unnecessary pauses. Do not ask extra clarification questions unless genuinely blocked or a decision belongs to the user.
- If verification is red, keep fixing the remaining failures instead of reporting status and stopping.
- Keep the scope aligned with the user’s request. Do not silently widen product scope, but do complete the verification scope required to call the task done.
- For bug fixes, add or update a regression test that proves the bug and then keep it passing with the fix.
- When architecture or behavior legitimately changes, update stale tests to the new contract instead of preserving invalid assumptions.
- Touch only what is needed for the task or for verification failures that must be fixed to get CI green.
- Prefer safe, reversible actions. Before any destructive git or filesystem action, inspect the current state first.
- Do not push, force-push, delete branches, or perform other shared-state actions unless the user explicitly asks.

## Repo-specific reminders

- Read and follow `Sagittarius_Elite_Warrior/.agents/rules/code-rule.md` when working in the app submodule.
- Do not modify protected strategy-engine files when the user has declared them out of scope.
- Treat runtime logs and failing checks as concrete evidence; fix the real cause, then rerun verification.
