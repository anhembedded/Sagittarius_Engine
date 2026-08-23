# TASK-017: Production Readiness Hardening

> **Completed 2026-08-23.** All 7 issues addressed, each with its own regression test (7 new
> tests; suite 698 → 705 passing). **Every checklist item was re-verified against the current
> tree before being touched**, per this repo's standing warning not to trust the checkboxes —
> and that mattered: **issue 3 was already fixed** (`TransactionMiddleware` had already been
> moved to `extensions/persistence/`; core `middleware/` has zero persistence references), so
> only its missing regression test was added. Item-by-item outcome below; details in the commit
> message.
>
> | # | Issue | Outcome |
> | :-- | :--- | :--- |
> | 1 | IPC broker deadlock | Fixed — `put()` now bounded by a `subscriber_put_timeout` (default 0.1s), `queue.Full` caught and the event dropped with a WARNING. |
> | 2 | DI container factory loss | Fixed — the lazy factory is restored on a failed `_resolve()`, so a transient failure no longer permanently destroys the registration. |
> | 3 | Core middleware coupled to extension | **Already fixed before this task**; added the missing regression test (boots the core with `sqlalchemy` sabotaged, asserts no `ImportError`). See TASK-031 for the related coupling this test uncovered one layer up. |
> | 4 | Deep hooking into CPython internals | Fixed — `DaemonThreadPoolExecutor` (which poked `concurrent.futures.thread._worker` / `._threads_queues`) deleted entirely; standard `ThreadPoolExecutor` + the already-present `shutdown(wait=False, cancel_futures=True)` is sufficient. |
> | 5 | Task-manager memory retention | Fixed — hardcoded `50` replaced by `task_manager.max_retained_tasks` via `IConfig`, resolved lazily and memoized, defaulting to 50 when no `IConfig` is registered. |
> | 6 | Audit WebSocket security | Bind default was **already** `127.0.0.1` (not `0.0.0.0` as the issue stated). Added the missing half: optional `auth_token`, validated from the `?token=` query parameter, rejecting with close code 4401 before any telemetry is sent. |
> | 7 | Incomplete graceful shutdown | Fixed — each of the 6 shutdown steps now runs on a bounded daemon thread (`step_timeout`, default 10s); a hanging step is logged and shutdown continues instead of blocking forever. |
>
> **Acceptance criteria status:** items 1, 2 and 4 (no regression) met. Item 3 — "CI passes with
> 100% success" — **not met, and deliberately not claimed**: the gate (`scripts/ci-local.ps1`)
> reports `RESULT: FAIL / FAILED_STEPS: Mypy,Tests`, at *exactly* the pre-existing baseline this
> task inherited — mypy's 24 known errors (`TASK-021` req. 5, zero of them in any file this task
> touched) and 2 pre-existing test failures (a QML font-directory warning that is local
> environment noise, and `.agents/context/repository.md`'s stale `sdk/` reference, `TASK-029`).
> Coverage is 85.34%, above the 80% bar. Per `rules/design-discipline.md`, closing this task does
> not weaken that criterion: it is unmet, it is unmet for reasons that predate this work, and
> those reasons are tracked elsewhere.

## Background
The Sagittarius Engine has reached a high level of maturity, but an architecture review identified several critical bugs, architectural risks, and bottlenecks that hinder 24/7 production readiness. This task consolidates these issues into a single hardening program.

## Objective
To resolve all identified critical bugs and architectural risks, ensuring the system is robust, memory-safe, secure, and fully decoupled. **Crucially, every issue must include a dedicated test case that reproduces the original failure/risk and guarantees coverage against future regressions.**

---

## Issue Checklist & Specifications

### [ ] 1. System Deadlock in IPC Broker
*   **Issue:** `IPCBroker` distributes events to `subscriber_queues` using `sub_queue.put((event_name, data))` without a timeout or `queue.Full` handling. If a subscriber hangs, the whole IPC bus deadlocks.
*   **Action:** Add a `timeout` (e.g., `0.1`) to the `put()` call. Catch `queue.Full` and gracefully drop the event with a warning log.
*   **Test Case Requirement:** Create a test that deliberately fills a subscriber's queue (or blocks a subscriber) and verifies that the `IPCBroker` does not block indefinitely when broadcasting a new event.

### [ ] 2. Factory Loss in DI Container on Error
*   **Issue:** In `StdContainer.singleton()`, the lazy factory immediately pops the factory from `_factories`. If `_resolve()` fails, the factory is permanently lost.
*   **Action:** Only remove the factory from `_factories` *after* `_resolve()` succeeds and the instance is safely stored in `_instances`.
*   **Test Case Requirement:** Create a test that attempts to resolve a singleton which initially fails (e.g., due to a temporarily missing dependency), then fix the condition, and assert that the second resolution attempt succeeds rather than failing with "Unregistered dependency".

### [ ] 3. Core Middleware Coupled to Extension
*   **Issue:** `TransactionMiddleware` inside the core engine directly imports `ISession` from `sagittarius_engine.extensions.persistence`. This breaks if the persistence extension is not used.
*   **Action:** Move `TransactionMiddleware` out of the core `middleware/` directory and into `extensions/persistence/`. The core should only provide the `IMiddleware` interface.
*   **Test Case Requirement:** Create a test environment (or test case) that initializes the core engine *without* the database extension installed, verifying that no `ImportError` occurs.

### [ ] 4. Deep Hooking into Python Internals
*   **Issue:** `DaemonThreadPoolExecutor` hacks into internal `concurrent.futures.thread` objects (`_worker`, `_threads_queues`) which is brittle across Python versions.
*   **Action:** Remove `DaemonThreadPoolExecutor`. Use the standard `ThreadPoolExecutor` and manage shutdown explicitly via `executor.shutdown(wait=False, cancel_futures=True)`.
*   **Test Case Requirement:** Write a test that validates the `TaskManager` can spawn tasks and shut down cleanly using the standard executor without leaving hanging threads.

### [ ] 5. Memory Leak Risk in Task Manager
*   **Issue:** `_cleanup_old_tasks()` retains up to 50 finished tasks indefinitely. This retains heavy payload closures in memory.
*   **Action:** Implement a TTL (Time-To-Live) mechanism or a strict `max_retained_tasks` configuration via `IConfig`. Clear tasks that exceed the retention policy.
*   **Test Case Requirement:** Write a test that completes a large number of tasks and asserts that they are successfully garbage collected / removed from the task dictionary after the TTL expires or retention limit is hit.

### [ ] 6. Security Flaw in Audit WebSocket
*   **Issue:** `WebsocketBroadcaster` defaults to binding on `0.0.0.0:9999` and broadcasts sensitive system state without authentication.
*   **Action:** Change the default bind address to `127.0.0.1`. Add a basic token authentication mechanism (e.g., verifying a `token=XYZ` query parameter upon connection).
*   **Test Case Requirement:** Write two tests:
    1. Verify connection is rejected if the token is missing or invalid.
    2. Verify successful connection and telemetry broadcast when a valid token is provided.

### [ ] 7. Incomplete Graceful Shutdown
*   **Issue:** `App.stop()` uses sequential `try...except` blocks. If any extension's `stop()` or `dispose()` hangs, the entire shutdown sequence blocks indefinitely.
*   **Action:** Wrap extension shutdown and disposal calls in a timeout mechanism (e.g., `asyncio.wait_for` for async hooks, or threading timeouts for synchronous ones) to guarantee `App.stop()` always completes.
*   **Test Case Requirement:** Create a rogue extension whose `stop()` method contains an infinite loop or `time.sleep(999)`. Write a test verifying that `App.stop()` still completes within a defined timeout threshold despite the rogue extension.

---

## Acceptance Criteria
- [ ] All 7 issues have been addressed in the source code.
- [ ] 7 distinct automated test cases have been added to reproduce the original bugs/risks and verify the fixes.
- [ ] CI pipeline (`lint.ps1` and GitHub Actions) passes with 100% success and 80%+ coverage.
- [ ] No regression in existing functionality.
