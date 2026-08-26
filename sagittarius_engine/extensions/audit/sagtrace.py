"""`.sagtrace` — save and re-open a recording offline (`EPIC-005C`, requirement 1).

@par Why a file format at all
Every other requirement in this subtask needs one: Perfetto opens a file, not a
running process, and verifying the OTel exporter without a live collector
means replaying a **saved** recording rather than a live one. This is the
thing both of those are built on.

@par Format
One JSON object: `{"hello": Hello.to_dict(), "records": [TraceRecord.to_dict(), ...]}`.
Plain JSON, not a bespoke binary format — a `.sagtrace` file is meant to be
readable with `jq` when the tooling that wrote it is not at hand, the same
argument `contracts.py` makes for the wire protocol.

`Hello` is included, not just the records: `dropped_before_connect` and
`epoch_wall_ns` are needed to render the trace honestly (a recording that lost
records to eviction should say so) and to convert monotonic offsets back to
wall-clock time for consumers like the OTel exporter.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .contracts import Hello, TraceRecord, check_protocol


def save_sagtrace(
    path: str | Path, hello: Hello, records: Iterable[TraceRecord]
) -> None:
    """@brief Writes a recording to `path`. Overwrites; this is a save, not an
    append log."""
    payload = {
        "hello": hello.to_dict(),
        "records": [r.to_dict() for r in records],
    }
    Path(path).write_text(json.dumps(payload), encoding="utf-8")


def load_sagtrace(path: str | Path) -> tuple[Hello, tuple[TraceRecord, ...]]:
    """
    @brief Reads a recording back.

    @raises ProtocolMismatch The file was written by a version this build
        cannot read — checked before anything else is parsed, the same rule
        `Envelope.from_dict()` applies to a live connection. A `.sagtrace` from
        an old version silently misread would be `D1` again, just offline.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    hello = Hello.from_dict(payload["hello"])
    check_protocol(hello.protocol_version)
    records = tuple(TraceRecord.from_dict(d) for d in payload["records"])
    return hello, records


def save_sagtrace_from_recorder(path: str | Path, recorder: Any) -> None:  # noqa: ANN401
    """
    @brief Convenience: pulls `hello()`/`snapshot()` off a recorder and saves.

    @param recorder Anything with `.hello()` and `.snapshot()` — the concrete
        `TraceRecorder`, not `ITraceRecorder`. The kernel-facing interface is
        deliberately minimal (`interfaces/i_trace_recorder.py`'s docstring
        explains why); reading a recording back out is tooling, not something
        an instrumentation site ever needs, so it is not part of that contract.
    """
    save_sagtrace(path, recorder.hello(), recorder.snapshot())
