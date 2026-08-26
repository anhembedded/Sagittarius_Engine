"""`sagittarius-trace` — attach to a running engine's trace stream (`EPIC-005D`).

@par What this does, and does not, do
Connects to a `TraceServer` (`infra/trace_server.py`) over WebSocket, prints
each record as a line of text as it arrives, and — with `--save` — writes
everything seen to a `.sagtrace` file when the connection ends. There is no
timeline widget and no aggregation: `EPIC-005` §5 already decided Perfetto
and the OTel exporter cover that ground better than a bespoke viewer would.
This exists only for the one thing they cannot do — watch an engine *live*.

@par Failing loudly at connect
`Envelope.from_dict()` calls `check_protocol()` before anything else about a
message is read. The very first thing received on any connection is the
server's `hello`, so a version mismatch surfaces as `ProtocolMismatch`
before a single record is printed — never a connection that just sits there
rendering nothing, which is exactly how the old dashboard's defect `D1`
looked from the operator's chair.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import signal
import sys
from collections.abc import Sequence
from typing import Any, TextIO

from .contracts import Envelope, Hello, MessageType, ProtocolMismatch, TraceRecord
from .sagtrace import save_sagtrace

#: See `extensions/diagnostics/cli.py` for the taxonomy this mirrors:
#: `EXIT_USAGE` covers everything short of "attached and streamed", because
#: none of those cases produced a trace worth trusting.
EXIT_OK = 0
EXIT_USAGE = 2


def _format_record(record: TraceRecord) -> str:
    seconds = record.t / 1_000_000_000
    parts = [f"[{seconds:12.6f}] {record.lane.value:<8} {record.name}"]
    if record.cat:
        parts.append(f"cat={record.cat}")
    if record.cid:
        parts.append(f"cid={record.cid}")
    if record.dur:
        parts.append(f"dur={record.dur}ns")
    if record.args is not None:
        parts.append(f"args={record.args}")
    return " ".join(parts)


def _recv_envelope(connection: Any) -> Envelope:
    """@raises ProtocolMismatch See `Envelope.from_dict()` — checked before
    the message's `type` or `data` is even looked at."""
    return Envelope.from_dict(json.loads(connection.recv()))


def attach(uri: str, save_path: str | None = None, out: TextIO = sys.stdout) -> int:
    """
    @brief Connects to `uri`, prints the live stream as text, and — with
    `save_path` — writes what it saw to a `.sagtrace` file when the
    connection ends (server disconnect or Ctrl+C).

    @return `EXIT_OK` on a clean detach, `EXIT_USAGE` if nothing worth
        trusting was ever produced — a failed connection, a peer that did not
        speak `hello` first, or a protocol mismatch at any point.
    """
    # Imported here, not at module level, for the same reason
    # `TraceServer._serve()` imports `websockets.asyncio.server` inside
    # itself: this is the one place an install without the transport's
    # runtime dependency would fail, and it should fail clearly at this exact
    # line rather than somewhere unrelated.
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect

    try:
        connection_cm = connect(uri)
    except OSError as exc:
        print(f"could not connect to {uri}: {exc}", file=sys.stderr)
        return EXIT_USAGE

    hello: Hello | None = None
    records: list[TraceRecord] = []
    try:
        with connection_cm as connection:
            try:
                envelope = _recv_envelope(connection)
            except ProtocolMismatch as exc:
                print(f"refusing to attach: {exc}", file=sys.stderr)
                return EXIT_USAGE

            if envelope.type is not MessageType.HELLO:
                print(
                    f"expected 'hello' first, got {envelope.type.value!r} — "
                    f"is {uri} really a sagittarius-trace server?",
                    file=sys.stderr,
                )
                return EXIT_USAGE

            hello = Hello.from_dict(envelope.data)
            print(
                f"attached to {uri} — protocol v{hello.protocol_version}, "
                f"capacity={hello.capacity}, "
                f"dropped_before_connect={hello.dropped_before_connect}",
                file=out,
            )

            while True:
                try:
                    envelope = _recv_envelope(connection)
                except ProtocolMismatch as exc:
                    print(f"peer sent an incompatible batch: {exc}", file=sys.stderr)
                    return EXIT_USAGE
                except ConnectionClosed:
                    break

                if envelope.type is not MessageType.TRACE:
                    continue
                for row in envelope.data:
                    record = TraceRecord.from_dict(row)
                    records.append(record)
                    print(_format_record(record), file=out)
    except KeyboardInterrupt:
        pass

    print("detached", file=out)
    if save_path is not None and hello is not None:
        save_sagtrace(save_path, hello, records)
        print(f"saved {len(records)} record(s) to {save_path}", file=out)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sagittarius-trace",
        description="Attach to a running engine's live trace stream.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    attach_parser = subparsers.add_parser(
        "attach", help="connect to a TraceServer and stream records as text"
    )
    attach_parser.add_argument(
        "uri", help="ws://host:port[?token=...] of a running TraceServer"
    )
    attach_parser.add_argument(
        "--save",
        metavar="PATH",
        default=None,
        help=(
            "on detach (Ctrl+C, or the server closing the connection), write "
            "everything seen this session to PATH as a .sagtrace file"
        ),
    )
    return parser


def _raise_keyboard_interrupt(signum: int, frame: object) -> None:
    raise KeyboardInterrupt


def main(argv: Sequence[str] | None = None) -> int:
    """
    @brief Entry point. Returns the exit code rather than calling `sys.exit`,
    so it is testable without catching `SystemExit`.

    @details Installs a `SIGTERM` handler, which `attach()` deliberately does
    not: a signal handler is process-global state that a library caller has
    not asked for, and this is the one place we own the process.

    Found by running the acceptance case under `timeout`, which sends
    `SIGTERM`: Python's default terminates without unwinding, so `--save`
    never ran and the file was silently absent — the same "you asked for
    output and got nothing, with no error" failure this whole epic exists to
    stop. `SIGTERM` is what a container stop, a systemd unit and a supervisor
    all send, which is most of the ways this command will actually be ended.
    """
    args = build_parser().parse_args(argv)
    with contextlib.suppress(ValueError):
        # ValueError: not on the main thread — a caller embedding this is not
        # the process owner, so having no handler is the correct outcome.
        signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    return attach(args.uri, args.save)


if __name__ == "__main__":  # pragma: no cover - exercised via the console script
    sys.exit(main())
