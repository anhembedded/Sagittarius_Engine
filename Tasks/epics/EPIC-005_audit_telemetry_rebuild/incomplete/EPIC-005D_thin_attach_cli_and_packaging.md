# EPIC-005D — Thin attach CLI, packaging, docs

**Epic:** [EPIC-005 — Audit Telemetry Teardown & Trace Recorder](../README.md)
**Status:** ⏸️ On hold with its epic
**Category:** Tooling / Packaging
**Priority:** P3
**Depends on:** EPIC-005C

---

## 🎯 Objective

One thin command that attaches to a running engine, streams the live event log and task stats,
and saves a `.sagtrace`.

## What this subtask is *not*

**No timeline widget.** `EPIC-005` §5 is the standing decision: no mainstream framework ships its
own trace viewer, `py-spy` and `viztracer` already cover most of what one would do, and Perfetto
renders the timeline better than we would. This milestone is roughly a tenth of what it was
before that scope cut.

Pressure to add "just a small timeline" will return. Reopening §5 needs a reason that `py-spy`,
`viztracer` and Perfetto together cannot cover — and **live streaming is the only known one**,
which is what this CLI provides in text.

## Requirements

1. From a built wheel in a clean venv, the command attaches to a running engine, streams the
   live event log, and writes a `.sagtrace`.
2. Version mismatch fails **loudly at connect**, never as a blank panel. This is the direct fix
   for D1, where a transport mismatch degraded into a permanent "connection error".
3. **Attach-late works**: start the app, run a workload, *then* attach — the retained buffer
   shows the workload that already finished.
4. Auth: rejected without a token when one is configured; binding off-loopback without a token is
   refused at startup.
5. `.agents/context/` updated; `TASK-002` marked superseded.

## Already guaranteed

The console script this adds is covered by `scripts/verify_wheel_importable.py` step 3 from the
moment it is declared (`TASK-039`). The failure that produced `TASK-002` — shipping a command
that had never run — cannot recur silently.
