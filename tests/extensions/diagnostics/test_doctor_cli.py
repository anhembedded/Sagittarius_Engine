"""`sagittarius-doctor` — the wiring inspection as a command (`EPIC-006E`).

Exercised through `main()` with an argv list rather than a subprocess: the
console script's *resolvability* is already guaranteed by
`scripts/verify_wheel_importable.py` step 3 (`TASK-039`), so what is left to
test is behaviour, and a subprocess would only make that slower and flakier.
"""

import json

import pytest

from sagittarius_engine.extensions.diagnostics import cli
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.kernel import App

_apps: list[App] = []


def _noop(data=None):
    return data


def clean_app():
    app = App(StdLibContainer(), MemoryEventBus())
    app.boot()
    _apps.append(app)
    return app


def app_with_a_typo():
    app = App(StdLibContainer(), MemoryEventBus())
    app.event_bus.on("app.bootd", _noop)  # A2 — an error
    app.boot()
    _apps.append(app)
    return app


def app_with_only_a_warning():
    app = App(StdLibContainer(), MemoryEventBus())
    app.event_bus.on("nothing.resembling.a.declared.name", _noop)
    app.boot()
    _apps.append(app)
    return app


not_callable = "I am a string"


class _SomeDependency:
    """Unbound, so the handler below gives the B checks something to report."""


class _HandlerWithADependency:
    """`HealthCheckQuery` takes no constructor arguments, so pointing the B
    checks at the health package finds a handler and reports nothing. This one
    has a dependency, which is what makes the check observable."""

    def __init__(self, dep: _SomeDependency) -> None:
        self._dep = dep

    def execute(self, dto):
        return None


@pytest.fixture(autouse=True)
def _stop_apps():
    yield
    while _apps:
        _apps.pop().stop()


# ------------------------------------------------------------- exit codes


def test_a_clean_application_exits_zero(capsys):
    assert cli.main([f"{__name__}:clean_app"]) == cli.EXIT_OK

    # Not "Wiring OK": that is reserved for a report with *no* findings at all,
    # and a bare engine still carries A1 advisories for its own lifecycle
    # events. Zero errors and zero warnings is the clean signal.
    out = capsys.readouterr().out
    assert "0 error(s), 0 warning(s)" in out


def test_a_wiring_error_exits_one(capsys):
    assert cli.main([f"{__name__}:app_with_a_typo"]) == cli.EXIT_FINDINGS

    out = capsys.readouterr().out
    assert "app.bootd" in out
    assert 'did you mean "app.booted"?' in out


def test_warnings_alone_pass_unless_strict():
    target = f"{__name__}:app_with_only_a_warning"

    assert cli.main([target]) == cli.EXIT_OK
    assert cli.main([target, "--strict"]) == cli.EXIT_FINDINGS


# --------------------------------------------- usage errors are distinct


def test_a_missing_colon_is_a_usage_error_not_a_finding(capsys):
    """EXIT_USAGE, so CI can tell 'wiring is wrong' from 'doctor could not run'."""
    assert cli.main(["myapp.main"]) == cli.EXIT_USAGE
    assert "missing ':'" in capsys.readouterr().err


def test_an_unimportable_module_is_a_usage_error(capsys):
    assert cli.main(["no.such.module:factory"]) == cli.EXIT_USAGE
    assert "cannot import" in capsys.readouterr().err


def test_a_missing_attribute_is_a_usage_error(capsys):
    assert cli.main([f"{__name__}:no_such_factory"]) == cli.EXIT_USAGE
    assert "no attribute" in capsys.readouterr().err


def test_a_non_callable_target_is_a_usage_error(capsys):
    assert cli.main([f"{__name__}:not_callable"]) == cli.EXIT_USAGE
    assert "not callable" in capsys.readouterr().err


def test_usage_errors_do_not_boot_anything(capsys):
    """Nothing should run when the arguments were never valid."""
    cli.main(["no.such.module:factory"])

    assert _apps == []


# ------------------------------------------------------------------ json


def test_json_output_parses(capsys):
    cli.main([f"{__name__}:app_with_a_typo", "--json"])

    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["counts"]["error"] == 1
    assert payload["findings"][0]["check"] == "A2"


def test_boot_output_does_not_corrupt_the_json(capsys):
    """An application that prints during boot must not break machine output.

    The engine's own logger writes to stdout, and unredirected it lands in the
    middle of the document.
    """

    def noisy_app():
        print("something an application printed while starting")
        return clean_app()

    globals()["noisy_app"] = noisy_app
    cli.main([f"{__name__}:noisy_app", "--json"])

    captured = capsys.readouterr()
    json.loads(captured.out)  # raises if the noise leaked into stdout
    assert "something an application printed" in captured.err


# --------------------------------------------------------------- options


def test_expect_unheard_silences_a1_for_that_event(capsys):
    cli.main([f"{__name__}:clean_app", "--json", "--expect-unheard", "app.booted"])

    payload = json.loads(capsys.readouterr().out)
    unheard = {f["subject"] for f in payload["findings"] if f["check"] == "A1"}

    assert "app.booted" not in unheard
    assert "app.ready" in unheard


def test_handler_package_enables_the_b_checks(capsys):
    cli.main([f"{__name__}:clean_app", "--json"])
    without = json.loads(capsys.readouterr().out)

    cli.main([f"{__name__}:clean_app", "--json", "--handler-package", __name__])
    with_handlers = json.loads(capsys.readouterr().out)

    assert not [f for f in without["findings"] if f["check"].startswith("B")]
    assert [f for f in with_handlers["findings"] if f["check"].startswith("B")]


# ------------------------------------- the reference application, in CI's shape


def test_the_reference_application_passes_strict_inspection(capsys):
    """What CI runs, asserted here so a break is a red test before it is a red build.

    `--strict` on purpose: the sample app is what this repository holds up as
    how to build on the engine, so a warning in it is a defect in the example.
    """
    exit_code = cli.main(
        [
            "examples.student_management.doctor_target:build",
            "--handler-package",
            "examples.student_management",
            "--strict",
        ]
    )

    assert exit_code == cli.EXIT_OK, capsys.readouterr().out


def test_the_reference_application_report_is_deterministic(capsys):
    """A report that varies between runs cannot be diffed or trusted in CI."""
    target = ["examples.student_management.doctor_target:build", "--json"]

    cli.main(target)
    first = capsys.readouterr().out
    cli.main(target)
    second = capsys.readouterr().out

    assert first == second
