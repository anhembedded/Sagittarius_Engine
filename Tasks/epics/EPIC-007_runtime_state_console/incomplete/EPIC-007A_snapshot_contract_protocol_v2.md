# EPIC-007A — Snapshot contract and protocol v2

**Epic:** [EPIC-007 — Runtime State Console](../README.md)
**Status:** 🟠 Not started
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
| `TaskState` | per retained task: id, name, state, progress, age, thread name, terminal error |
| `ThreadPoolStats` | per pool: name, max workers, in flight, queue depth, submitted, completed |
| `BoundedStructures` | ring fill/capacity/dropped, retained tasks/limit, subscription counts, `gc.get_count()` |
| `ConfigState` | per key: key, source, value **or** mask |
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
