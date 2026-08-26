"""
Infrastructure layer for the audit extension — the live trace transport.

`WebsocketBroadcaster` was removed here by `EPIC-005A`'s teardown. Its
replacement is `TraceServer` in `trace_server.py`, which kept the parts of it
that worked (ephemeral port, a readiness event, `?token=` auth rejected with
close code `4401`) and dropped the snapshot-broadcast model it served.

Not re-exported: importing it here would pull `websockets` in at package
import time, and the engine's own core does not depend on the transport —
only the CLI and an application that explicitly starts a server do.
"""
