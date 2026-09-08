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
import time
from collections.abc import Sequence
from typing import Any, TextIO

from .contracts import (
    Envelope,
    Hello,
    MessageType,
    ProtocolMismatch,
    StateSnapshot,
    TraceRecord,
)
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


def _format_snapshot(snapshot: StateSnapshot) -> str:
    """
    @brief `EPIC-007C` §2.5's text rendering — a panel hides a missing field
    behind blank space; this cannot, because every section is its own line
    and an absent one is simply not there.
    """
    lines: list[str] = [f"snapshot @ {snapshot.t / 1_000_000_000:.6f}s"]

    if snapshot.lifecycle is not None:
        lc = snapshot.lifecycle
        lines.append(
            f"lifecycle: state={lc.state} "
            f"extensions={lc.extensions_initialized}/{lc.extensions_registered} "
            f"hosted={lc.hosted_started}/{lc.hosted_registered} "
            f"scheduler_jobs={lc.scheduler_jobs} "
            f"(without_next_run={lc.scheduler_jobs_without_next_run})"
        )

    if snapshot.events:
        lines.append(f"events: {len(snapshot.events)}")
        for event in snapshot.events:
            flag = "" if event.registered else " [UNREGISTERED]"
            lines.append(
                f"  {event.name}{flag} handlers={len(event.handlers)} "
                f"emits={event.emits} failures={event.failures}"
            )

    if snapshot.container is not None:
        container = snapshot.container
        lines.append(
            f"container: {len(container.registrations)} registration(s), "
            f"open_scopes={container.open_scopes}"
        )
        for reg in container.registrations:
            state = "instantiated" if reg.instantiated else "not instantiated"
            lines.append(
                f"  {reg.abstract} -> {reg.concrete or '?'} [{reg.lifetime}] {state}"
            )

    if snapshot.tasks:
        lines.append(f"tasks: {len(snapshot.tasks)}")
        for task in snapshot.tasks:
            error = f" error={task.error!r}" if task.error else ""
            lines.append(
                f"  {task.id} name={task.name!r} state={task.state} "
                f"progress={task.progress:.0%} age={task.age_ns / 1_000_000_000:.1f}s"
                f"{error}"
            )

    if snapshot.thread_pools:
        lines.append("thread pools:")
        for pool in snapshot.thread_pools:
            lines.append(
                f"  {pool.name}: {pool.in_flight}/{pool.max_workers} in flight, "
                f"queue_depth={pool.queue_depth}, submitted={pool.submitted}, "
                f"completed={pool.completed}"
            )

    if snapshot.bounded is not None:
        bounded = snapshot.bounded
        lines.append(
            f"bounded: ring={bounded.ring_used}/{bounded.ring_capacity} "
            f"(dropped={bounded.ring_dropped}), "
            f"tasks={bounded.retained_tasks}/{bounded.retained_task_limit}, "
            f"subscriptions={bounded.subscriptions}, "
            f"gc_counts={list(bounded.gc_counts)}"
        )

    if snapshot.config:
        noun = "entry" if len(snapshot.config) == 1 else "entries"
        lines.append(f"config: {len(snapshot.config)} {noun}")
        for entry in snapshot.config:
            value = "***" if entry.masked else entry.value
            source = f" (source={entry.source})" if entry.source else ""
            lines.append(f"  {entry.key}={value}{source}")

    if snapshot.findings:
        lines.append(f"findings: {len(snapshot.findings)}")
        for finding in snapshot.findings:
            lines.append(f"  [{finding.severity}] {finding.subject}: {finding.message}")

    if snapshot.signals is not None:
        signals = snapshot.signals
        if signals.dead_letters:
            lines.append(f"dead letters: {len(signals.dead_letters)}")
            for dl in signals.dead_letters:
                lines.append(
                    f"  {dl.event_name}: {dl.exception_type}: {dl.exception_message} "
                    f"(handler={dl.handler}, retries={dl.retries})"
                )
        if signals.state_machines:
            lines.append(f"state machines: {len(signals.state_machines)}")
            for machine in signals.state_machines:
                lines.append(
                    f"  {machine.name}: state={machine.current_state} "
                    f"rejected={machine.rejected_count}"
                )
                for transition in machine.transitions:
                    flag = " [REJECTED]" if transition.rejected else ""
                    via = f" via {transition.event}" if transition.event else ""
                    lines.append(
                        f"    {transition.from_state} -> {transition.to_state}"
                        f"{via}{flag}"
                    )
        if signals.ui_thread is not None:
            ui_thread = signals.ui_thread
            lines.append(
                f"ui thread: freezes={ui_thread.freeze_count} "
                f"(worst={ui_thread.worst_freeze_ms:.0f}ms), "
                f"off_thread_mutations={ui_thread.off_thread_mutation_count}"
            )

    return "\n".join(lines)


def _parse_duration(text: str) -> float:
    """@brief `"1s"`, `"500ms"`, or a bare number of seconds -- the same
    small grammar as everywhere else a human types a duration into this CLI.
    @raises ValueError For anything else, so `argparse` reports it as a
    usage error rather than the watch loop failing on its first tick."""
    text = text.strip()
    if text.endswith("ms"):
        return float(text[:-2]) / 1000.0
    if text.endswith("s"):
        return float(text[:-1])
    return float(text)


def snapshot(
    uri: str,
    watch_seconds: float | None = None,
    out: TextIO = sys.stdout,
) -> int:
    """
    @brief Connects to `uri`, requests one `StateSnapshot` (any inbound frame
    triggers one — `EPIC-007C` §2.4), prints it as text, and — with
    `watch_seconds` — repeats on that interval until detached (Ctrl+C, or the
    server closing the connection).

    @return `EXIT_OK` on a clean detach, `EXIT_USAGE` if nothing worth
        trusting was ever produced — a failed connection, a peer that did not
        speak `hello` first, or a protocol mismatch at any point.
    """
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect

    try:
        connection_cm = connect(uri)
    except OSError as exc:
        print(f"could not connect to {uri}: {exc}", file=sys.stderr)
        return EXIT_USAGE

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

            while True:
                try:
                    connection.send("snapshot")
                    envelope = _recv_envelope(connection)
                except ProtocolMismatch as exc:
                    print(f"peer sent an incompatible message: {exc}", file=sys.stderr)
                    return EXIT_USAGE
                except ConnectionClosed:
                    break

                if envelope.type is MessageType.SNAPSHOT:
                    print(
                        _format_snapshot(StateSnapshot.from_dict(envelope.data)),
                        file=out,
                    )
                elif envelope.type is MessageType.ERROR:
                    print(
                        f"server error: {envelope.data.get('detail')}", file=sys.stderr
                    )

                if watch_seconds is None:
                    break
                print("", file=out)
                time.sleep(watch_seconds)
    except KeyboardInterrupt:
        pass

    print("detached", file=out)
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

    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="request one StateSnapshot from a TraceServer and print it as text",
    )
    snapshot_parser.add_argument(
        "uri", help="ws://host:port[?token=...] of a running TraceServer"
    )
    snapshot_parser.add_argument(
        "--watch",
        metavar="DURATION",
        default=None,
        help=(
            "keep the connection open and request a fresh snapshot every "
            "DURATION (e.g. '1s', '500ms') until detached; a single snapshot "
            "is requested and printed once when omitted"
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
    if args.command == "snapshot":
        try:
            watch_seconds = None if args.watch is None else _parse_duration(args.watch)
        except ValueError:
            print(f"--watch: not a duration: {args.watch!r}", file=sys.stderr)
            return EXIT_USAGE
        return snapshot(args.uri, watch_seconds)
    return attach(args.uri, args.save)


if __name__ == "__main__":  # pragma: no cover - exercised via the console script
    sys.exit(main())
