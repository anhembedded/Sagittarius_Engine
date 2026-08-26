"""A spawned task's progress update is visible on the handle the task manager
tracks — not just on the local reference the caller happens to hold.

@par Rewritten by `EPIC-005A`'s teardown, deliberately not deleted
This read the progress back through `AuditService.get_all_tasks_details()`,
which was removed with the rest of the snapshot dashboard. The behaviour under
test is the task manager's, not the audit extension's, so the test is kept and
pointed at the real surface instead.

That is also a better test than it was. `get_all_tasks_details()` reached the
task manager through four chained `getattr`/`hasattr` guesses
(`getattr(context, "tasks", None)`, `hasattr(tm, "tasks")`, an
`isinstance(..., dict)` branch, `hasattr(t, "error")`), so any of them silently
falling through produced an empty list — and an empty list would have failed
this test's own `found` assertion with "Task should be in output", pointing at
the task manager for what would have been the collector's bug.
"""

from __future__ import annotations

from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.kernel.app import App


def test_progress_set_on_a_spawned_task_is_visible_on_the_tracked_handle():
    app = App(StdLibContainer(), MemoryEventBus())
    app.boot()

    def long_running_task(token):
        pass

    handle = app.context.tasks.spawn(long_running_task, name="UploadFile")
    handle.update_progress(45.5, "Uploading chunk 2")

    # Read it back off the manager's own registry rather than off `handle`:
    # asserting on the object we just called would pass even if the manager
    # tracked something else entirely.
    tracked = app.context.tasks.tasks[handle.id]

    assert tracked.progress == 45.5
    assert tracked.status.value in ("running", "completed")
