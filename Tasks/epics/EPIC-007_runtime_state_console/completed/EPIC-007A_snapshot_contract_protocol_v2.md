# EPIC-007A — Snapshot contract and protocol v2

**Epic:** [EPIC-007 — Runtime State Console](../README.md)
**Status:** ✅ **Done 2026-08-27** — see §Outcome
**Category:** Observability / Protocol
**Priority:** P2
**Depends on:** nothing — this is the groundwork

---

## 1. Why this is first, and why it is a whole milestone

`EPIC-005` §2's D3 and D4 are one defect written twice: the engine and the dashboard each
kept their own idea of the payload, and they drifted until the consumer was reading fields
the producer had stopped sending. `contracts.py` exists to make that impossible, and states
its own terms:

> There is now exactly one schema, here, and **the client imports it rather than
> redeclaring it**. A drift of that kind should become an `ImportError` or a type error, not
> a panel that quietly goes blank.

Everything downstream in this epic — the collector, the text rendering, the QML client —
is a consumer of what this milestone defines. Getting it wrong is cheap now and expensive at
`EPIC-007E`.

## 2. Scope

### 2.1 The dataclasses

In `sagittarius_engine/extensions/audit/contracts.py`, beside `TraceRecord` and `Hello`, and
under the same rules: `frozen=True, slots=True`, stdlib only, `to_dict()` producing
primitives, `from_dict()` taking defaults for absent optional keys, **nothing formatted at
capture**.

| Type | Carries |
| :--- | :--- |
| `StateSnapshot` | `t` (ns since session epoch), the sections below, and `findings` |
| `LifecycleState` | current `EngineState`, the transitions reached with their timestamps, extension/hosted/scheduler counts |
| `EventState` | per event: name, declaring module, handler count and qualnames, emit count, failure count |
| `ContainerState` | per registration: abstract, concrete, lifetime, `instantiated`; plus open-scope count |
| `TaskRecord` | per retained task: id, name, state, progress, age, thread name, terminal error |
| `ThreadPoolStats` | per pool: name, max workers, in flight, queue depth, submitted, completed |
| `BoundedStructures` | ring fill/capacity/dropped, retained tasks/limit, subscription counts, `gc.get_count()` |
| `ConfigEntry` | per key: key, source, value **or** mask |
| `FindingRecord` | the wire form of `diagnostics.report.Finding` — `check`, `severity`, `subject`, `message`, `hint` |

`FindingRecord` mirrors an existing type rather than reusing it directly: `Finding` lives in
`extensions/diagnostics/` and `contracts.py` must stay importable by a client that has no
reason to pull in the diagnostics package. The mapping is one function and is covered by a
test that fails if `Finding` grows a field this does not carry.

### 2.2 Protocol version

`PROTOCOL_VERSION` 1 → 2. `check_protocol()` stays an equality check — it is a function
precisely so that widening happens in one place for both sides of the wire, and v2 has no
backward-compatible predecessor either.

**A v1 `sagittarius-trace` therefore refuses a v2 server, loudly, at connect.** That is the
designed behaviour and is stated in `ADR-001` §3: the alternative is what `EPIC-005` D1
actually shipped — a client that reported a connection error forever and presented an empty
panel that read as "nothing is happening".

### 2.3 Secret masking lives here

`ConfigState` carries either a value or a mask, never both, and the masking decision is made
**engine-side** before the record is built. A client cannot request an unmasked value; the
only way to see one is an explicit opt-in on the engine at construction. `ADR-001` §2.8.

Default masked-key patterns: `*secret*`, `*token*`, `*password*`, `*key*`, `*dsn*`, and any
URL-shaped value carrying userinfo. Case-insensitive. The key and its source are always
shown — "which layer won" is what a config panel is opened for.

## 3. How to run it

```bash
# the round-trip, and the masking rule
.venv/bin/python -m pytest tests/extensions/audit/test_snapshot_contract.py -v

# the version handshake, both directions
.venv/bin/python -m pytest tests/extensions/audit/test_snapshot_contract.py -k protocol -v
```

There is no live process to attach to yet — that is `EPIC-007C`. What runs here is the
schema's own proof.

## 4. Done when

1. `to_dict()` → `from_dict()` is lossless for every type, including the empty and
   all-optional cases.
2. Omitted optional keys take their defaults, so the byte-saving omissions `TraceRecord`
   already makes are safe here too.
3. `check_protocol(1)` raises `ProtocolMismatch` naming **both** versions.
4. A test asserts `FindingRecord` carries every field of `diagnostics.report.Finding`, and
   fails if `Finding` gains one.
5. A test asserts a secret-shaped key is masked by default and that no field on the wire can
   turn masking off.
6. `contracts.py` still imports with **stdlib only** — enforced by the existing architecture
   test, extended if it does not already cover this module.

---

# Outcome

**Done 2026-08-27.** `contracts.py` 312 → 869 lines; 23 new tests; the audit suite is
89 passed / 12 skipped (the skips are the optional `otel` extra, unchanged).

## What shipped

`PROTOCOL_VERSION` 1 → 2, and nine shapes beside `TraceRecord`/`Hello`: `StateSnapshot`,
`LifecycleState`, `EventState`, `RegistrationState`, `ContainerState`, `TaskRecord`,
`ThreadPoolStats`, `BoundedStructures`, `ConfigEntry`, `FindingRecord` — plus
`mask_config()` and `snapshot_message()`.

## Three decisions taken while writing it

**Readable keys, not `TraceRecord`'s single letters.** That terseness is a measured response
to a 10k-events/sec stream, where *"the difference between sending `"cat": ""` and sending
nothing is most of the bandwidth"*. A snapshot is collected at 1 Hz at most (`ADR-001` §2.4),
so the pressure does not exist, and paying for it anyway would buy nothing and cost every
reader who pipes the wire through `jq`. Same module, different budget — stated in a comment
there so the inconsistency reads as a decision rather than an oversight.

**`TaskRecord`, not the specified `TaskState`.** `runtime.tasks.TaskState` is the engine's
own enum, and two things sharing a name one import apart is precisely what `EventRegistry`'s
collision warning exists to catch. The enum's *value* travels as the record's `state` field.
This file's §2.1 table is corrected.

**Value masking checks the value, not only the key.** `database.url` matches no
secret-shaped pattern and is the most common real credential in this engine's own sample
configuration (`postgresql://app:hunter2@db/prod`). `_has_userinfo()` catches the URL whose
key name gives nothing away — the one case a key-name allowlist would have missed entirely.

## A test that was passing for the wrong reason

`tests/extensions/audit/test_cli.py`'s
`test_a_peer_that_does_not_speak_hello_first_is_refused` hardcoded `{"v": 1, …}`. Correct
while the protocol *was* v1; the moment v2 landed that peer became a **version** mismatch
too, so the refusal the test asserts would have come from `check_protocol()` rather than
from the missing `hello` the test is named for. It would still have passed, and would have
stopped testing anything. Changed to `PROTOCOL_VERSION`, with the reason at the line.

This is `design-discipline.md`'s rubber-stamp failure arriving on its own rather than being
introduced — worth recording because nothing would have reported it.

## Deviation from criterion 6

Criterion 6 said the stdlib-only check goes in `tests/test_architecture.py` *"extended if it
does not already cover this module"*. It went in
`test_snapshot_contract.py::test_contracts_imports_nothing_but_the_stdlib_and_engine_interfaces`
instead — the rule it enforces is stated in `contracts.py`'s own docstring, so the test reads
better beside the module it is about. If a second schema module ever appears, promote it.

## Verified

| Gate | Result |
| :--- | :--- |
| `pytest tests/extensions/audit` | **89 passed, 12 skipped** |
| `pytest tests/ --ignore=…/pyside_mvc --ignore=…/ui_state` | **930 passed, 22 skipped** |
| `ruff check sagittarius_engine tests examples tools` | **All checks passed** |
| `ruff format --check sagittarius_engine tests examples tools` | **424 files already formatted** |
| `mypy sagittarius_engine tests examples tools --ignore-missing-imports --follow-imports=skip` | **1 error, none in changed files** |

Two pre-existing environmental failures, neither caused by this change and both reproducing
on the unmodified tree:

- **8 × `test_all_modules_importable`** — `PySide6` is not installed in this container. CI
  installs `requirements.txt`, so these pass there.
- **`test_agents_docs_resolve::test_staleness_check_actually_catches_the_original_bug`** —
  runs `git show 0bd461b:…`, and this is a **shallow clone** (`.git/shallow` present), so
  that object is absent. `git cat-file -t 0bd461b` → *"Not a valid object name"*.

The single mypy error is `thread_affinity.py:124`, which `ci.yml` documents by name as the
false positive produced when PySide6 is absent: *"the same command with PySide6 present
reports `Success: no issues found in 436 source files`."*

## Run it

```bash
.venv/bin/python -m pytest tests/extensions/audit/test_snapshot_contract.py -v
```
