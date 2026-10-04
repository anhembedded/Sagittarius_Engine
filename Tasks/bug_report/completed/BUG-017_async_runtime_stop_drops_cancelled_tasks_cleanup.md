# BUG-017 — `AsyncRuntime.stop()` drops the cleanup of every task it cancels

**Reported date:** 2026-10-04
**Severity:** Low. Nothing crashes. At shutdown the interpreter prints `Task was destroyed but it is pending!`, and any connection a task held (an `aiohttp` session, a websocket) is dropped instead of closed.
**Status:** ✅ Fixed (2026-10-04). The drain landed in PR #227, green on GitHub Actions (all 8 checks on `11ad014`). Its review found three gaps, closed in the follow-up PR (see "Review follow-up").
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
- Any task still pending after the drain's budget is named in a WARNING, by the name it was spawned with (see "Review follow-up").
- It is skipped when the loop is not running, or when `stop()` is called from the loop's own thread, where waiting would deadlock.

The `cancelling()` check is load-bearing. Cancelling a task a second time aborts the `await` inside its `finally`. That was the first draft's mistake, and it is pinned by a mutation check (below).

## Regression test

`tests/runtime/test_async_runtime_stop_drains_tasks.py`:

- `test_stop_runs_the_finally_of_a_task_cancelled_just_before_it`: red before the fix (`assert [] == ['closed']`), green after.
- `test_stop_cancels_a_running_task_and_runs_its_finally`: red before the fix, green after.
- `test_stop_does_not_wait_past_its_timeout_for_a_task_that_ignores_cancel`: keeps the drain bounded.

Mutation: dropping the `cancelling()` check turns the first test red again.

## Review follow-up

The independent review of PR #227 found three things. All three are fixed in the follow-up PR.

1. **`App.stop()` could return with the loop still running.** The drain could use the whole `timeout`, which is also the step budget `App.stop()` gives `async_runtime.stop()`. A task that never finished cancelling therefore spent all of it, `App.stop()` set the lifecycle to `stopped`, and the loop kept running on an abandoned thread.
   - `timeout` is now one deadline for the whole call. The drain gets half of it, including `shutdown_asyncgens()`, and the join gets the rest.
   - `test_app_stop_leaves_the_loop_closed_when_a_task_ignores_cancel` checks that the loop is closed when `App.stop(step_timeout=0.5)` returns.
2. **The tests did not prove that the drain waits.** Setting the drain's timeout to 0, or removing it altogether, still passed.
   - Both cleanup tests now await 50 ms in their `finally`.
   - The stubborn-task test asserts the WARNING and returns within `timeout` plus 0.25 s.
   - A new test calls `stop()` from the loop thread and must return in under 0.2 s, which pins the guard that skips the drain there.
3. **The WARNING named tasks `Task-N`.** `TaskManager._wrap_coro` now gives the asyncio task its spawned name, so the warning names `stubborn` or `SpotUserDataStream`.

Every mutation the review listed now turns at least one test red:
- the drain's timeout set to 0, or removed;
- the `cancelling()` check dropped;
- the loop-thread guard dropped;
- the task naming dropped;
- the old drain that used the full `timeout`.

## Verification

- PR #227: `scripts/ci-local.ps1` PASS (1648 passed, 11 skipped), and GitHub Actions green on `11ad014`.
- The follow-up: the five tests in `tests/runtime/test_async_runtime_stop_drains_tasks.py` pass, and the full gate result is in its PR.
