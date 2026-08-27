"""Protocol v2's snapshot shapes — `EPIC-007A`.

Every test here exists because of a named defect in `EPIC-005` §2, not because
a dataclass deserves coverage:

- `D3`/`D4` — producer and consumer each kept their own idea of the payload and
  drifted until the consumer was reading fields the producer had stopped
  sending. The round-trip tests are what make a drift fail here rather than go
  blank on a panel.
- `D1` — a version mismatch that was tolerated, producing an empty view that
  read as "nothing is happening". `test_a_v1_peer_is_refused_naming_both_versions`
  is that mismatch being refused out loud instead.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import sys

import pytest

from sagittarius_engine.extensions.audit.contracts import (
    PROTOCOL_VERSION,
    BoundedStructures,
    ConfigEntry,
    ContainerState,
    Envelope,
    EventState,
    FindingRecord,
    LifecycleState,
    MessageType,
    ProtocolMismatch,
    RegistrationState,
    StateSnapshot,
    TaskRecord,
    ThreadPoolStats,
    check_protocol,
    mask_config,
    snapshot_message,
)
from sagittarius_engine.extensions.diagnostics.report import Finding

# --------------------------------------------------------------------- fixtures


def _populated_snapshot() -> StateSnapshot:
    """@brief A snapshot with every section non-empty and every optional set,
    so a round-trip that silently drops one has something to drop."""
    return StateSnapshot(
        t=1_234_567_890,
        lifecycle=LifecycleState(
            state="READY",
            transitions=(
                ("CREATED", 0),
                ("BOOTING", 11_000_000),
                ("READY", 1_284_000_000),
            ),
            extensions_registered=5,
            extensions_initialized=5,
            hosted_registered=2,
            hosted_started=2,
            scheduler_jobs=3,
            scheduler_jobs_without_next_run=1,
        ),
        events=(
            EventState(
                name="student.deleted",
                module="domain.events",
                handlers=("RosterPresenter.on_removed",),
                emits=38,
                failures=4,
            ),
            EventState(name="student.updatd", handlers=("X.y",), registered=False),
        ),
        container=ContainerState(
            registrations=(
                RegistrationState(
                    abstract="IConfig",
                    concrete="ConfigManager",
                    lifetime="singleton",
                    instantiated=True,
                ),
                RegistrationState(abstract="IClock", lifetime="singleton"),
            ),
            open_scopes=3,
        ),
        tasks=(
            TaskRecord(
                id="a3f10c2e",
                name="export_roster_pdf",
                state="RUNNING",
                progress=0.62,
                age_ns=4_200_000_000,
                thread="SagittariusBgTask_1",
            ),
            TaskRecord(id="90bb3c17", name="import_csv", state="FAILED", error="boom"),
        ),
        thread_pools=(
            ThreadPoolStats(
                name="background",
                max_workers=20,
                in_flight=2,
                queue_depth=7,
                submitted=611,
                completed=609,
            ),
        ),
        bounded=BoundedStructures(
            ring_used=12_480,
            ring_capacity=100_000,
            ring_dropped=0,
            retained_tasks=47,
            retained_task_limit=100,
            subscriptions=18,
            gc_counts=(318, 7, 2),
        ),
        config=(
            ConfigEntry(key="ui.theme", source="json:config.json", value="dark"),
            ConfigEntry(key="api_token", source="env:APP_", masked=True),
        ),
        findings=(
            FindingRecord(
                check="A2",
                severity="error",
                subject="student.updatd",
                message="a handler is subscribed to this name",
                hint='did you mean "student.updated"?',
            ),
        ),
    )


# ------------------------------------------------------------------ round-trip


def test_a_populated_snapshot_survives_a_round_trip_unchanged():
    original = _populated_snapshot()
    assert StateSnapshot.from_dict(original.to_dict()) == original


def test_an_empty_snapshot_survives_a_round_trip_unchanged():
    """The all-defaults case. `to_dict()` omits every absent section, so this
    is where an omission that cannot be reconstructed would show up."""
    original = StateSnapshot()
    assert StateSnapshot.from_dict(original.to_dict()) == original


@pytest.mark.parametrize(
    "instance",
    [
        LifecycleState(),
        EventState(name="e"),
        RegistrationState(abstract="A"),
        ContainerState(),
        TaskRecord(id="t"),
        ThreadPoolStats(name="p"),
        BoundedStructures(),
        ConfigEntry(key="k"),
        FindingRecord(check="c", severity="info", subject="s", message="m"),
    ],
    ids=lambda i: type(i).__name__,
)
def test_each_shape_round_trips_at_its_defaults(instance):
    assert type(instance).from_dict(instance.to_dict()) == instance


def test_absent_optional_keys_take_their_defaults():
    """The property that makes `to_dict()`'s omissions safe: a consumer reading
    a minimal payload must land on the same object a full one describes."""
    assert TaskRecord.from_dict({"id": "x"}) == TaskRecord(id="x")
    assert EventState.from_dict({"name": "e"}) == EventState(name="e")
    assert StateSnapshot.from_dict({}) == StateSnapshot()


def test_a_snapshot_travels_whole_inside_an_envelope():
    original = _populated_snapshot()
    envelope = snapshot_message(seq=7, snapshot=original)

    assert envelope.type is MessageType.SNAPSHOT
    assert envelope.seq == 7

    received = Envelope.from_dict(envelope.to_dict())
    assert StateSnapshot.from_dict(received.data) == original


# ------------------------------------------------------------------- protocol


def test_protocol_version_is_two():
    assert PROTOCOL_VERSION == 2


def test_a_v1_peer_is_refused_naming_both_versions():
    """`D1` is what tolerating this looks like: a client that reported a
    connection error forever and showed an empty panel."""
    with pytest.raises(ProtocolMismatch) as excinfo:
        check_protocol(1)

    message = str(excinfo.value)
    assert "v1" in message
    assert f"v{PROTOCOL_VERSION}" in message


# --------------------------------------------------------------------- masking


def test_a_secret_shaped_key_is_masked_by_default():
    entries = {e.key: e for e in mask_config({"api_token": "abc", "ui.theme": "dark"})}

    assert entries["api_token"].masked is True
    assert entries["api_token"].value is None
    assert entries["ui.theme"].masked is False
    assert entries["ui.theme"].value == "dark"


def test_a_url_carrying_credentials_is_masked_even_though_its_key_is_innocent():
    """`database.url` matches no secret-shaped pattern, and is the most common
    real credential in this engine's own sample configuration."""
    (entry,) = mask_config({"database.url": "postgresql://app:hunter2@db/prod"})

    assert entry.masked is True
    assert entry.value is None


def test_a_url_without_credentials_is_not_masked():
    (entry,) = mask_config({"database.url": "sqlite:///students.db"})

    assert entry.masked is False
    assert entry.value == "sqlite:///students.db"


def test_revealing_is_a_producer_side_decision_only():
    """`reveal` is keyword-only on the producer, and no field on the wire can
    reach it: a client must not be able to ask a server to disclose more than
    it was configured to disclose (`ADR-001` §2.8)."""
    (revealed,) = mask_config({"api_token": "abc"}, reveal=True)
    assert revealed.value == "abc"

    # A payload claiming both a mask and a value does not get to keep the
    # value. Masking is decided before the record is built, and re-reading one
    # cannot undo it.
    smuggled = ConfigEntry.from_dict(
        {"key": "api_token", "masked": True, "value": "abc"}
    )
    assert smuggled.value is None
    assert smuggled.masked is True


def test_a_masked_entry_never_puts_its_value_on_the_wire():
    (entry,) = mask_config({"password": "hunter2"})
    assert "value" not in entry.to_dict()
    assert "hunter2" not in repr(entry.to_dict())


def test_the_key_and_its_source_survive_masking():
    """ "Which layer won" is the question a config panel is opened for, and it
    is answerable without disclosing anything."""
    (entry,) = mask_config({"api_token": "abc"}, sources={"api_token": "env:APP_"})

    assert entry.key == "api_token"
    assert entry.source == "env:APP_"
    assert entry.to_dict()["source"] == "env:APP_"


# ------------------------------------------------------- mirror, not a second copy


def test_finding_record_carries_every_field_finding_has():
    """`FindingRecord` mirrors `diagnostics.report.Finding` so that
    `contracts.py` stays importable without pulling in the diagnostics package.
    A mirror that silently falls behind is `D3`/`D4`, so it is guarded: this
    fails the moment `Finding` grows a field."""
    finding_fields = {f.name for f in dataclasses.fields(Finding)}
    record_fields = {f.name for f in dataclasses.fields(FindingRecord)}

    missing = finding_fields - record_fields
    assert not missing, (
        f"Finding has field(s) {sorted(missing)} that FindingRecord does not "
        "carry — add them here and to to_dict()/from_dict(), or the console "
        "will silently stop showing them."
    )


# ------------------------------------------------------------------- layering


def test_contracts_imports_nothing_but_the_stdlib_and_engine_interfaces():
    """`contracts.py` is imported by the engine *and* by any consumer attaching
    to it. A third-party import here would put a dependency on both sides of a
    wire whose whole purpose is to be attachable from anywhere — the module's
    own docstring is the rule this enforces."""
    source = pathlib.Path("sagittarius_engine/extensions/audit/contracts.py").read_text(
        encoding="utf-8"
    )

    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    for module in imported:
        root = module.split(".")[0]
        if root == "sagittarius_engine":
            assert module.startswith("sagittarius_engine.interfaces"), (
                f"contracts.py imports {module!r} — only the engine's own "
                "interfaces may be reached from the shared schema."
            )
            continue
        if root == "__future__":
            continue
        assert root in sys.stdlib_module_names, (
            f"contracts.py imports third-party module {module!r}; the schema "
            "must stay stdlib-only so both sides of the wire can import it."
        )
