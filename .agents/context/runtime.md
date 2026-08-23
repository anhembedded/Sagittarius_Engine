# Runtime Operations

The Sagittarius Engine Runtime is responsible for orchestrating background processes, managing threads/tasks, and maintaining the deterministic lifecycle of the application.

## Key Subsystems

### 1. TaskManager (`ITaskManager`)
Manages background threads and async coroutines.
- **`spawn()`**: Spawns a background execution (sync function or async coroutine). Returns a `BackgroundTask`.
- **Cancellation**: Passes a `CancellationToken` to tasks so they can cooperatively exit.
- **Events**: Emits `TaskStarted`, `TaskProgressUpdated`, `TaskCompleted`, and `TaskFailed` over the `EventBus`.

### 2. AsyncRuntime
A thin wrapper around `asyncio` that allows synchronous engine code to fire-and-forget or await asynchronous coroutines deterministically. Used extensively by `TaskManager`.

### 3. Scheduler
Handles recurring and delayed jobs.
- **Triggers**: `IntervalTrigger`, `CronTrigger`.
- Used by health checks or periodic cleanup tasks.

### 4. Hosted Services (`IHostedService`)
Services that start with the application and run continuously until shutdown.
- **`BackgroundService`**: An abstract base class implementing `IHostedService`. It automatically hooks into the `TaskManager` to spawn a long-running daemon loop (`run(self, token: CancellationToken)`), completely non-blocking to the main engine thread.
- Examples include background queue consumers or a long-running CLI menu loop. No shipped
  extension currently subclasses `BackgroundService` for a CLI presentation layer — the sample
  app's CLI (`examples/student_management`) is a synchronous `argparse` command, not a hosted
  service; verified 2026-08-23, replacing a previous version that named a `TerminalMenu` class
  that doesn't exist anywhere in this repo.
