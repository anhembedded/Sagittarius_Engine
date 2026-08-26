"""Trace recording (`EPIC-005`).

`AuditExtension` and `AuditService` were removed here by `EPIC-005A`'s
teardown — they collected a snapshot of *now* and could never answer "what
happened", which is the only question a trace tool exists for. See
`.agents/context/tracing.md`.

Nothing is re-exported eagerly. `TraceRecorder` is the entry point
(`recorder.py`), and the exporters and transport each pull dependencies —
`websockets`, and the `[otel]` extra — that importing this package must not
require.
"""
