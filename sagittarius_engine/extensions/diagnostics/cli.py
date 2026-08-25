"""`sagittarius-doctor` — run the wiring inspection from a shell.

`EPIC-006B` produces a `WiringReport`; this is a rendering of it with an exit
code, so a mis-wiring becomes a red build rather than a runtime surprise.

@par What it necessarily does
It **boots the application**. Wiring does not exist until something wires it,
so there is no way to inspect it without running the application's own
composition. That is the one thing this tool does that the checks themselves
refuse to do, and it is worth knowing before pointing it at production
configuration: the factory you name runs, with whatever side effects it has.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .handlers import discover_handlers
from .inspector import WiringInspector
from .report import WiringReport

#: Exit codes. Distinct so CI can tell "your wiring is wrong" from "the doctor
#: could not run", which need different responses from whoever sees the build.
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2


class UsageError(Exception):
    """
    @brief The operator mistyped an argument.

    @details Distinct from a wiring finding, and reported as `EXIT_USAGE`, so CI
    can tell "your wiring is wrong" from "the doctor could not run" — those need
    different responses from whoever reads the build.

    Raised rather than `SystemExit`: `SystemExit(str)` always exits `1`, which
    would have made the two indistinguishable while the constants above claimed
    otherwise.
    """


def load_factory(target: str) -> Any:
    """
    @brief Resolves `"package.module:callable"` to the callable.

    @details The working directory goes on `sys.path` first. A console script
    does not inherit it the way `python script.py` does, so without this the
    obvious invocation — `cd myproject && sagittarius-doctor myapp.main:build_app`
    — fails with `No module named 'myapp'`.

    Needing one specific working directory is one of the three faults that kept
    `sagittarius-audit` from ever running (`TASK-039`). The difference here is
    that it is deliberate, documented, and what a user pointing a tool at their
    own project expects.

    @raises UsageError Naming what was wrong, rather than a traceback: every
        failure here is a mistyped argument, not a defect in the application
        under inspection.
    """
    if ":" not in target:
        raise UsageError(f"{EXIT_USAGE_HINT}\n  got: {target!r} (missing ':')")

    cwd = str(Path.cwd())
    if "" not in sys.path and cwd not in sys.path:
        sys.path.insert(0, cwd)

    module_name, _, attribute = target.partition(":")

    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise UsageError(f"cannot import {module_name!r}: {exc}") from exc

    factory = getattr(module, attribute, None)
    if factory is None:
        raise UsageError(f"{module_name!r} has no attribute {attribute!r}")
    if not callable(factory):
        raise UsageError(f"{target!r} is not callable")

    return factory


EXIT_USAGE_HINT = (
    "expected an application factory as 'package.module:callable' — "
    "for example 'myapp.main:build_app'"
)


def _as_json(report: WiringReport) -> str:
    return json.dumps(
        {
            "ok": report.ok,
            "counts": {
                "error": len(report.errors),
                "warning": len(report.warnings),
                "info": len(report.infos),
            },
            "findings": [asdict(f) for f in report.sorted_findings()],
        },
        indent=2,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sagittarius-doctor",
        description=(
            "Inspect a Sagittarius application's wiring and report what does "
            "not add up. Boots the application in order to do so."
        ),
    )
    parser.add_argument(
        "factory",
        help="application factory, as 'package.module:callable' (returns an App)",
    )
    parser.add_argument(
        "--handler-package",
        action="append",
        default=[],
        metavar="PREFIX",
        help=(
            "search this package for dispatchable handlers (checks B1-B3). "
            "Repeatable. Without it, handlers are not checked — they are in no "
            "registry, so there is nothing to enumerate them from."
        ),
    )
    parser.add_argument(
        "--expect-unheard",
        action="append",
        default=[],
        metavar="EVENT",
        help=(
            "an event this application deliberately does not listen to; "
            "silences check A1 for it. Repeatable."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the report as JSON instead of text",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero on warnings as well as errors",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    @brief Entry point. Returns the exit code rather than calling `sys.exit`,
    so it is testable without catching `SystemExit`.
    """
    args = build_parser().parse_args(argv)

    try:
        factory = load_factory(args.factory)
    except UsageError as exc:
        print(exc, file=sys.stderr)
        return EXIT_USAGE

    # Booting is noisy, and this application's logger writes to stdout. In
    # `--json` mode that noise lands in the middle of the document and makes it
    # unparseable — measured, not assumed. Diagnostics belong on stderr and the
    # payload on stdout, so the boot's output is redirected rather than the
    # report being moved out of the caller's way.
    with contextlib.redirect_stdout(sys.stderr):
        app = factory()

    context = app.context
    handlers = discover_handlers(*args.handler_package) if args.handler_package else ()

    report = WiringInspector().inspect(
        bus=context.event_bus,
        container=context.container,
        extension_manager=getattr(context, "extension_manager", None),
        hosted_services=getattr(context, "hosted_services", None),
        scheduler=getattr(context, "scheduler", None),
        expected_unheard=args.expect_unheard,
        handlers=handlers,
    )

    print(_as_json(report) if args.json else report.format())

    if report.errors:
        return EXIT_FINDINGS
    if args.strict and report.warnings:
        return EXIT_FINDINGS
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised via the console script
    sys.exit(main())
