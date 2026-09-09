"""`count_signals` — `EPIC-008B` §2's rail badge counts.

Pure function over a `StateSnapshot`, deliberately not a new wire field
(`reference/handoff.md` §6: "a fault badge appears... when that section's
signal count > 0" — a *display* concern, derived from data the snapshot
already carries, the same way `OverviewPresenter` already derives
`snapshotAgeSeconds` from timestamps rather than the server sending an
"age" field). Kept in its own module, independent of Qt, so the counting
rules are testable without a `TraceServer` or a `QApplication` — the same
reasoning `tools/state_console/domain/events.py`'s `_DEFAULT_CODE_BY_KIND`
earned its own pure-Python test file for.

Each count mirrors a rule `reference/handoff.md` already states elsewhere
for the same data, not an invented threshold:

- **events** — undeclared event names (`EventState.registered is False`),
  the same set §7.3's own "WIRING BUG" banner counts.
- **container** — deliberately `0` for now. §7.4's "scope leak suspected"
  needs a trend ("climbing since attach"), which a single snapshot cannot
  show; `ContainerState.open_scopes` alone is a count, not a signal. Real
  leak detection belongs to `EPIC-008` subtask D (Container restyle), which
  will have a place to keep history across snapshots.
- **tasks** — failed tasks (`TaskRecord.state == "failed"`, `TaskState`'s
  own wire value) plus broken scheduler jobs
  (`LifecycleState.scheduler_jobs_without_next_run`) — §7.5's own two
  named signals ("Failed" tasks, jobs with "no next fire").
- **signals** — dead letters plus rejected state-machine transitions
  (`StateMachineState.rejected_count`) — §7.6's own "dead letters +
  rejections" pairing, and the exact pairing named for the Overview →
  Status "Signals" plate in §7.1.
- **overview** — the sum of the four above, the same total that plate
  shows ("N open" / "All clear").
"""

from __future__ import annotations

from sagittarius_engine.extensions.audit.contracts import StateSnapshot


def count_signals(snapshot: StateSnapshot) -> dict[str, int]:
    events = sum(1 for e in snapshot.events if not e.registered)

    container = 0

    tasks = sum(1 for t in snapshot.tasks if t.state == "failed")
    if snapshot.lifecycle is not None:
        tasks += snapshot.lifecycle.scheduler_jobs_without_next_run

    signals = 0
    if snapshot.signals is not None:
        signals += len(snapshot.signals.dead_letters)
        signals += sum(m.rejected_count for m in snapshot.signals.state_machines)

    return {
        "events": events,
        "container": container,
        "tasks": tasks,
        "signals": signals,
        "overview": events + container + tasks + signals,
    }
