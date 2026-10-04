# BUG-017 — `AsyncRuntime.stop()` drops the cleanup of every task it cancels

**Reported date:** 2026-10-04
**Severity:** Low. Nothing crashes. At shutdown the interpreter prints `Task was destroyed but it is pending!`, and any connection a task held (an `aiohttp` session, a websocket) is dropped instead of closed.
**Status:** 🔴 Open. The fix is on branch `claude/wizardly-cerf-fc5b5x`; this report closes once that change is green on GitHub Actions (the lesson of `BUG-014`'s two premature local closures).
**Found by:** the reference consumer's first live Spot Testnet run of its user-data stream (`Sagittarius_Elite_Warrior` `BUG-143`)

---

## What is wrong

`AsyncRuntime.stop()` (`sagittarius_engine/runtime/async_runtime/async_runtime.py`) did its steps in this order:

1. Call `loop.stop`.
2. Join the loop's thread.
3. Call `task.cancel()` on every task still pending.
4. Call `loop.close()`.

A task cancelled after its loop has stopped never runs again. Its `finally` blocks are dropped, and the coroutine is garbage-collected while `cancelling`.

The usual way into this is a consumer that cancels its own task just before the app stops. `TaskManager`'s handle cancels the `concurrent.futures.Future` from `run_coroutine_threadsafe`, which only *schedules* `task.cancel()` on the loop, and the loop stops before the task can unwind.

The reference consumer met it as:

```
Task was destroyed but it is pending!
task: <Task cancelling name='Task-1' coro=<TaskManager._wrap_coro() running at ...\task_manager.py:190> wait_for=<Future cancelled> ...>
Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x...>
```

## Reproduction

Use `App(StdLibContainer(), MemoryEventBus())` and start its `async_runtime`. Spawn a coroutine with `tasks.spawn()` that awaits `sleep(3600)` inside `try/finally`; its `finally` awaits once and then records a flag. Cancel the handle, then call `async_runtime.stop()`.

The flag is never set. Every time.

## Fix

`stop()` now drains the loop before stopping it (`AsyncRuntime._drain`):

- It runs a coroutine on the loop that cancels every other task not already `cancelling()`.
- It awaits those tasks with `asyncio.wait(..., timeout)`, then calls `loop.shutdown_asyncgens()`.
- It names any task still pending after `timeout`, with a WARNING.
- It is skipped when the loop is not running, or when `stop()` is called from the loop's own thread, where waiting would deadlock.

The `cancelling()` check is load-bearing. Cancelling a task a second time aborts the `await` inside its `finally`. That was the first draft's mistake, and it is pinned by a mutation check (below).

## Regression test

`tests/runtime/test_async_runtime_stop_drains_tasks.py`:

- `test_stop_runs_the_finally_of_a_task_cancelled_just_before_it`: red before the fix (`assert [] == ['closed']`), green after.
- `test_stop_cancels_a_running_task_and_runs_its_finally`: red before the fix, green after.
- `test_stop_does_not_wait_past_its_timeout_for_a_task_that_ignores_cancel`: keeps the drain bounded.

Mutation: dropping the `cancelling()` check turns the first test red again.

## Verification

Local: the three tests pass, and the reproduction above sets its flag with no warning. The full gate is pending: `scripts/ci-local.ps1` locally, then GitHub Actions on the PR.
