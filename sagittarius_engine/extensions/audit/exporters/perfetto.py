"""Perfetto exporter (`EPIC-005C`, requirement 2).

@par Why this comes before any UI
Perfetto validates the trace model against a viewer nobody here wrote. If the
instrumentation or the model is wrong, an encoder this size makes that visible
within a day — before any UI work is committed to it. There is no cheaper way
to find out the model is wrong.

@par Format
Chrome's JSON Trace Event Format, which `ui.perfetto.dev` opens natively with
no conversion step. Stdlib only — `json`, nothing else — because a diagnostic
export must never become a soft requirement of the core path.

@par How a record becomes an event
The recorder writes **two** rows per span: a begin marker (`dur=0`, written by
`span_begin()`) and an end marker (`dur>0`, written by `span_end()`, whose own
`t` is the *end* time). A closed span's full interval is already in its end
marker alone (`t - dur` .. `t`), so only end markers are encoded here — the
begin marker is redundant for a closed span and is always skipped, not just
when a span happens to still be open.

@warning `SPAN` records with `dur == 0` are **not** all "still open" — every
completed span has exactly one, by design. This encoder does not need to tell
the two cases apart (both are correctly excluded: a closed span is fully
described by its end marker, and a genuinely open span has no end to draw),
but a caller counting `dur == 0` records to estimate open spans would be
wrong on every trace — see `exporters/otel.py`'s `_count_unclosed()` for the
correct way, needed there because that exporter *does* report a count.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..contracts import Lane, RecordKind, TraceRecord

#: Chrome Trace Format time unit is microseconds; the engine records in
#: nanoseconds. One constant rather than a magic number at every conversion
#: site.
_NS_PER_US = 1_000

#: Stable per-lane track id. Fixed order (not, say, sorted by first
#: appearance) so two exports of the same kind of application put each
#: subsystem on the same track number — comparing two traces side by side in
#: Perfetto is easier when "dispatch" is always track 4, not whatever track it
#: happened to appear on first.
_LANE_TRACK_ID: dict[Lane, int] = {lane: index + 1 for index, lane in enumerate(Lane)}

#: A fixed, single process. This exporter has no concept of multiple
#: processes — every record in one `TraceRecorder` came from one process by
#: construction (`time.perf_counter_ns()` is process-local).
_PID = 1


def to_perfetto_trace(records: Iterable[TraceRecord]) -> dict[str, Any]:
    """
    @brief Builds a Chrome Trace Event Format document from captured records.

    @details Two passes: the first discovers which lanes actually appear, so
    the metadata events (process/thread names) only name tracks that have
    something on them — an application using three of nine lanes gets three
    rows in Perfetto, not nine mostly-empty ones. The second pass emits the
    events themselves.

    @return A dict with a `"traceEvents"` key, ready for `json.dumps()`.
        Returned as data rather than written to a file directly: a caller
        merging several recordings, or embedding this in a larger document,
        should not have to parse it back out of a file to do that.
    """
    records = tuple(records)
    used_lanes = {r.lane for r in records}

    events: list[dict[str, Any]] = [
        {
            "ph": "M",
            "pid": _PID,
            "name": "process_name",
            "args": {"name": "sagittarius-engine"},
        }
    ]
    for lane in Lane:
        if lane in used_lanes:
            events.append(
                {
                    "ph": "M",
                    "pid": _PID,
                    "tid": _LANE_TRACK_ID[lane],
                    "name": "thread_name",
                    "args": {"name": lane.value},
                }
            )

    for record in records:
        event = _encode(record)
        if event is not None:
            events.append(event)

    return {"traceEvents": events, "displayTimeUnit": "ns"}


def write_perfetto_trace(path: str, records: Iterable[TraceRecord]) -> None:
    """@brief `to_perfetto_trace()`, written to `path` as JSON."""
    Path(path).write_text(json.dumps(to_perfetto_trace(records)), encoding="utf-8")


def _encode(record: TraceRecord) -> dict[str, Any] | None:
    """@brief One record to one Chrome Trace event, or `None` if it does not
    represent a drawable interval or instant — see the module docstring for
    why a `SPAN` with `dur == 0` is skipped rather than encoded as a point."""
    common = {
        "name": record.name,
        "cat": record.cat,
        "pid": _PID,
        "tid": _LANE_TRACK_ID[record.lane],
    }
    args = dict(record.args) if record.args else {}
    if record.cid:
        # Not used to nest across tracks here — Perfetto's JSON importer nests
        # purely by track and interval containment, which this encoder relies
        # on. Kept as a searchable attribute: "find every event from this one
        # dispatch" is a real question to ask of a trace, even without a flow
        # arrow drawn for it.
        args["cid"] = record.cid

    if record.kind is RecordKind.SPAN:
        if record.dur == 0:
            return None
        return {
            **common,
            "ph": "X",
            "ts": (record.t - record.dur) / _NS_PER_US,
            "dur": record.dur / _NS_PER_US,
            "args": args,
        }

    # RecordKind.INSTANT
    return {
        **common,
        "ph": "i",
        "ts": record.t / _NS_PER_US,
        "s": "t",  # thread-scoped: draws on the lane's own track
        "args": args,
    }
