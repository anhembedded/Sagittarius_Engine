"""Trace exporters (`EPIC-005C`).

Two, deliberately asymmetric:

- `perfetto` — stdlib only, always available. Perfetto validates the trace
  model against a viewer nobody here wrote, before any UI work is committed
  to it — see `EPIC-005` §5.
- `otel` — behind the `[otel]` extra. Importing this package never imports
  `otel`; that module guards its own dependency so uninstalling the extra
  leaves everything else in this package working (`EPIC-005C` requirement 4).
"""
