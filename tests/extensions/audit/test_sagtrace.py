"""`.sagtrace` — save and re-open a recording offline (`EPIC-005C` requirement 1).

Everything both exporters need is built on this: Perfetto opens a file, not a
running process, and verifying the OTel exporter without a live collector
means replaying a *saved* recording.
"""

from __future__ import annotations

import json

import pytest

from sagittarius_engine.extensions.audit.contracts import (
    Hello,
    Lane,
    ProtocolMismatch,
    RecordKind,
    TraceRecord,
)
from sagittarius_engine.extensions.audit.recorder import TraceRecorder
from sagittarius_engine.extensions.audit.sagtrace import (
    load_sagtrace,
    save_sagtrace,
    save_sagtrace_from_recorder,
)


def test_a_recording_round_trips_through_disk(tmp_path):
    hello = Hello(
        epoch_wall_ns=1_700_000_000_000_000_000, capacity=100, dropped_before_connect=2
    )
    records = (
        TraceRecord(t=100, kind=RecordKind.INSTANT, lane=Lane.USER, name="mark"),
        TraceRecord(
            t=500, kind=RecordKind.SPAN, lane=Lane.TASK, name="run", dur=400, cid=1
        ),
    )
    path = tmp_path / "recording.sagtrace"

    save_sagtrace(path, hello, records)
    restored_hello, restored_records = load_sagtrace(path)

    assert restored_hello == hello
    assert restored_records == records


def test_the_file_is_plain_json_readable_without_this_librarys_help(tmp_path):
    """`contracts.py` argues for a wire format a human can read with `jq` when
    the tooling that wrote it is not at hand. The saved file is that same
    argument applied to disk."""
    hello = Hello()
    records = (TraceRecord(t=1, kind=RecordKind.INSTANT, lane=Lane.USER, name="x"),)
    path = tmp_path / "recording.sagtrace"

    save_sagtrace(path, hello, records)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["hello"]["v"] == hello.protocol_version
    assert raw["records"][0]["n"] == "x"


def test_loading_a_future_protocol_version_fails_before_records_are_parsed(tmp_path):
    """The same rule `Envelope.from_dict()` applies to a live connection,
    applied here to a file: a `.sagtrace` from a version this build cannot
    read must fail loudly, not silently misread — that degradation is `D1`,
    just offline."""
    path = tmp_path / "future.sagtrace"
    path.write_text(
        json.dumps(
            {
                "hello": {**Hello().to_dict(), "v": Hello().protocol_version + 99},
                "records": [{"not": "even parseable as a record"}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProtocolMismatch):
        load_sagtrace(path)


def test_saving_overwrites_rather_than_appends(tmp_path):
    path = tmp_path / "recording.sagtrace"
    save_sagtrace(
        path,
        Hello(),
        (TraceRecord(t=1, kind=RecordKind.INSTANT, lane=Lane.USER, name="a"),),
    )
    save_sagtrace(
        path,
        Hello(),
        (TraceRecord(t=2, kind=RecordKind.INSTANT, lane=Lane.USER, name="b"),),
    )

    _, records = load_sagtrace(path)
    assert [r.name for r in records] == ["b"]


def test_save_from_recorder_pulls_hello_and_snapshot(tmp_path):
    recorder = TraceRecorder(capacity=10)
    recorder.instant(Lane.USER, "order-filled", args={"price": 101.5})
    path = tmp_path / "recording.sagtrace"

    save_sagtrace_from_recorder(path, recorder)

    hello, records = load_sagtrace(path)
    assert hello.capacity == 10
    assert records[0].name == "order-filled"
    assert records[0].args == {"price": 101.5}
