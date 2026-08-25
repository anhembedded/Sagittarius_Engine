# EPIC-005C — `.sagtrace`, Perfetto and OpenTelemetry exporters

**Epic:** [EPIC-005 — Audit Telemetry Teardown & Trace Recorder](../README.md)
**Status:** ⏸️ On hold with its epic
**Category:** Observability / Interoperability
**Priority:** P2
**Depends on:** EPIC-005B

---

## 🎯 Objective

Get the trace out to tools that already exist, rather than building a viewer.

## Why this comes before any UI

Perfetto validates the trace model **against a viewer nobody here wrote**. If the instrumentation
or the model is wrong, that becomes visible within a day of an encoder that is roughly 100 lines
— before any UI work is committed to it. There is no cheaper way to find out the model is wrong.

The OTel exporter is the part that matters for the epic's stated goal. For a framework aiming to
be credible in professional use, **standard spans are worth more than any bespoke viewer**:
Jaeger, Tempo, Grafana and Datadog are already running where this framework wants to be taken
seriously, and a bespoke UI is something a team must learn and has no reason to trust.

## Requirements

1. `.sagtrace` — save and re-open a recording offline.
2. **Perfetto**: a recording of the demo app opens in `ui.perfetto.dev` with correct lanes and
   nested spans.
3. **OpenTelemetry**: the same run appears in a local OTLP collector with correct parent/child
   structure. Mapping table in `EPIC-005` §5.1.
4. **The `[otel]` extra is genuinely optional.** Uninstalling it leaves the core working — the
   engine's stdlib-only core rule is not negotiable for a diagnostic feature, and the exporter
   must never become a soft requirement of the core path.
