# EPIC-005C — `.sagtrace`, Perfetto and OpenTelemetry exporters

**Epic:** [EPIC-005 — Audit Telemetry Teardown & Trace Recorder](../README.md)
**Status:** ✅ **Done 2026-08-26** — see §Outcome. Requirements 2/3 verified structurally, not
by literally opening `ui.perfetto.dev` or a live OTLP collector — neither is available in this
environment. See §Outcome for what that verification actually was.
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

---

# Outcome

## What shipped

| | Requirement | Where |
| :--- | :--- | :--- |
| 1 | `.sagtrace` save/reopen | `extensions/audit/sagtrace.py` |
| 2 | Perfetto exporter | `extensions/audit/exporters/perfetto.py` — stdlib only, ~140 lines |
| 3 | OpenTelemetry exporter | `extensions/audit/exporters/otel.py` — behind `[otel]` |
| 4 | `[otel]` genuinely optional | verified by uninstalling it and re-running the core, see below |

`.sagtrace` is plain JSON — `{"hello": ..., "records": [...]}` — for the same reason
`contracts.py` argues for the wire protocol: a human with `jq` should be able to read one when
the tooling that wrote it is not at hand. `load_sagtrace()` calls `check_protocol()` before
parsing a single record, so a file from a version this build cannot read fails loudly — `D1`
again, just offline.

## How requirements 2 and 3 were actually verified

Neither `ui.perfetto.dev` nor a local OTLP collector is reachable from this environment — no
browser, no collector process. Both were verified structurally instead:

- **Perfetto**: every emitted event is checked against Chrome Trace Event Format's own shape
  (`ph`/`ts`/`dur`/`pid`/`tid` per event kind), and — the part that actually matters — a real
  dispatch through a fully `EPIC-005B`-instrumented `App` is exported, then its middleware and
  handler intervals are asserted to nest inside the dispatch total's interval. That containment
  is exactly what Perfetto's own importer relies on to draw a flame graph at all; if it did not
  hold, the trace would not render correctly regardless of what a browser showed.
- **OpenTelemetry**: replayed into the SDK's own `InMemorySpanExporter`, which records precisely
  the spans a real collector would receive, one layer before OTLP wire encoding. Parent/child
  links, start/end times, and attributes are asserted directly on the SDK's `ReadableSpan`
  objects.

This is the same class of substitution used elsewhere in this repository — verifying the
`libEGL` system-library failure by reproducing both directions in a matching venv rather than
asserting it — applied to "no collector available" rather than "no display server available."

## Reconstructing parent/child from a flat record stream

The recorder stores no parent pointer, only a correlation id shared by the records of one
dispatch (`kernel/dispatcher.py` mints one per call, used only synchronously within it). Spans
sharing one id are therefore **properly nested by construction** — a stack-based interval sweep,
sorted by start ascending and end descending as a tie-break, reconstructs the tree exactly.

Records with `cid == 0` — extension boot spans, task-run spans, and everything the application
records through `ctx.trace` — carry no grouping at all. Each becomes an **independent
single-span trace**, and an orphan `ctx.trace.mark()` becomes a single-point span carrying one
event so the mapping table's "instant → span event" rule holds even with nothing to attach it
to. This is an honest simplification, recorded here rather than silently narrowed: a nicer
result (one shared "boot" trace for every extension span) is additional design, not a defect in
this one.

## A real bug, found by running the exporter and reading the number

Every span the recorder captures writes **two** rows: a begin marker (`dur == 0`) and an end
marker (`dur > 0`). The first version of the OTel exporter's `unclosed` return value counted
every `dur == 0` record directly — which is every span's own begin marker, present on a
perfectly normal, fully closed span. Running it against a real, fully-`stop()`ed demo
application reported:

```
otel: 6 spans replayed from the SAVED FILE, unclosed=5
```

Five "unclosed" spans, from a run where nothing was open. A caller checking `if unclosed: warn(...)`
would have fired on every single call. Not caught by any synthetic unit test, because those
tests only ever constructed the end marker directly — the one real end-to-end test that used
actual `recorder.snapshot()` output checked span content and parent links but never looked at
the returned count.

Fixed in `_count_unclosed()`: begin and end markers are counted separately per
`(lane, name, cat, cid)` — the four values every instrumentation site passes identically to both
`span_begin()` and `span_end()` — and the deficit (`max(0, begins - ends)`) is summed per key.
That handles the same key occurring more than once (the same handler dispatched twice with
`cid=0`) without needing to identify *which* specific begin marker is unmatched, only *how
many*. Re-run against the same demo: `unclosed=0`. A regression test locks in both the
false-positive case (a clean run must report `0`) and that a genuinely open span mixed among
closed ones is still found.

The Perfetto encoder's actual behaviour was unaffected — it already skipped every `dur == 0`
record unconditionally, which is correct whether the record is a closed span's redundant begin
marker or a genuinely open span with nothing to draw — but its docstring made the same "still
open" claim and was corrected for the same reason: a comment that is confidently wrong about
common data is worse than one that is silent about the edge case.

## `[otel]` is genuinely optional, verified rather than assumed

With `opentelemetry-sdk` and its OTLP exporter uninstalled from the venv: `mypy` stays clean
(`ignore_missing_imports` treats the unresolved import as `Any` in both directions — checked
with the package present and absent), the core imports and boots an application successfully,
and calling into the exporter raises `OTelNotInstalled` naming the fix rather than an
`ImportError` a reader would have to decode. `opentelemetry-sdk` is listed in
`requirements-dev.txt` (not `requirements.txt`) for the same reason `pytest-qt` is — so CI
actually exercises `test_otel.py` rather than it skipping everywhere, including there.

## Verification

23 new tests (5 `.sagtrace`, 7 Perfetto, 11 OTel). Full suite **1366 passed, 11 skipped**,
coverage 91.24%; `ruff`, `ruff format --check` and `mypy` clean; architecture guard passes;
`sagittarius-doctor` still exits 0 on the reference application.
