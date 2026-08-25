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
import traceback
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .handlers import discover_handlers
from .inspector import WiringInspector
from .report import WiringReport

#: Exit codes. Distinct so CI can tell "your wiring is wrong" from "the doctor
#: could not run", which need different responses from whoever sees the build.
#:
#: `EXIT_USAGE` is named narrower than it means. It covers everything in the
#: second category -- a mistyped argument, a module that raises while being
#: imported, a factory that dies before returning an `App` -- because they all
#: share the property that matters to a build: **no wiring was inspected**.
#: Reporting any of them as `EXIT_FINDINGS` would claim an inspection happened
#: and found errors, which is a different and false statement. The name is kept
#: rather than corrected because it is the published contract of a shipped
#: console script; the meaning is recorded here instead.
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2


class UsageError(Exception):
    """
    @brief The doctor could not get as far as inspecting anything.

    @details Distinct from a wiring finding, and reported as `EXIT_USAGE`, so CI
    can tell "your wiring is wrong" from "the doctor could not run" — those need
    different responses from whoever reads the build.

    Raised rather than `SystemExit`: `SystemExit(str)` always exits `1`, which
    would have made the two indistinguishable while the constants above claimed
    otherwise.

    @par Correction (2026-08-25)
    This said "the operator mistyped an argument", and `load_factory()` said
    every failure in it was "a mistyped argument, not a defect in the
    application under inspection". Both were false, and demonstrably so: naming
    a module whose *module-level code* raises, or a factory that dies before
    returning an `App`, escaped as a bare traceback and exit `1` — which this
    file's own constants define as "inspected the wiring, found errors". Nothing
    had been inspected.

    The application starts running the moment its module is imported, so a
    failure here is very often a defect in it. What these failures have in
    common is not whose fault they are; it is that no report exists.
    """


class TargetError(UsageError):
    """
    @brief The target was named correctly, but running it failed.

    @details A subclass rather than a sibling: callers that only care whether a
    report exists can keep catching `UsageError`, while the message can still
    say which of the two happened. An operator reading a build needs that
    difference — "you typed the wrong module" and "your application crashed on
    boot" are not the same next action.
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

    @raises UsageError The argument itself is wrong — no colon, no such module,
        no such attribute, or an attribute that is not callable.
    @raises TargetError The argument named something real, but importing it
        raised. Importing runs the module's top-level code, so this reaches
        anything an application does at import time; the original traceback is
        chained rather than swallowed, because for this case it is the whole
        diagnosis.
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
    except Exception as exc:
        # Deliberately broad. Importing runs the module's top-level code, which
        # is arbitrary application code and can raise anything at all -- this
        # was found by a `TypeError` from a module-level registration call
        # escaping as a raw traceback under exit 1.
        raise TargetError(
            f"importing {module_name!r} raised {type(exc).__name__}: {exc}"
        ) from exc

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
    #
    # The factory is the one place this tool runs someone else's code on
    # purpose, so it is also the one place an arbitrary exception is expected
    # rather than exceptional. Letting it escape produced a bare traceback under
    # exit 1 — which this file defines as "wiring inspected, errors found", a
    # claim that is false when the application never finished booting.
    try:
        with contextlib.redirect_stdout(sys.stderr):
            app = factory()
    except Exception:
        # The traceback is printed, not summarised: it points at the line in the
        # application that failed, and no message this tool composes can be more
        # useful than that.
        traceback.print_exc()
        print(
            f"\n{args.factory} raised while building the application. "
            "Nothing was inspected — this is not a wiring report.",
            file=sys.stderr,
        )
        return EXIT_USAGE

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
