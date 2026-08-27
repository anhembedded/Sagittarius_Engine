# ADR-002: The state console's first client is a **terminal renderer**; the graphical client is **PySide6 + QML**, and it comes second

- **Status**: 🟠 Proposed
- **Date**: 2026-08-27
- **Category**: Observability / Tooling / Packaging
- **Depends on**: [`ADR-001`](ADR-001_runtime_state_console_scope_and_transport.md) — this ADR
  decides only what *renders* the snapshot that ADR defines
- **Relates to**: `7a3ac18` (QtWidgets kit removed from the engine), `TASK-038`,
  `EPIC-005` §2 D7/D10, `EPIC-001` (UI Engine Foundation), `ui-architecture.md`

---

## 1. Context

[`ADR-001`](ADR-001_runtime_state_console_scope_and_transport.md) settles what data leaves
the process and how. It deliberately says nothing about pixels. This ADR answers the
question that was raised against it: **which UI framework, and why has nobody argued for
one?**

The answer is not free-choice. Five constraints already in force narrow it hard, and four
of them are written down in this repository as the outcome of something that went wrong.

### 1.1 The wheel declares zero dependencies — and that is what killed the last client

`pyproject.toml` declares no `[project] dependencies` at all. The only extra is `otel`.
`EPIC-005` §2 D7:

> The wheel is zero-dependency by design, but `tools/audit_dashboard/main.py` imports
> `PySide6.QtWidgets` at module level. A real `pip install sagittarius-engine` therefore
> yields a `sagittarius-audit` command that dies on `ModuleNotFoundError: No module named
> 'PySide6'` before reaching any of its own code.

The pattern that replaced it works and is the precedent to copy: `sagittarius-trace` needs
`websockets`, and neither `extensions/audit/cli.py` nor `infra/trace_server.py` imports it
at module scope — the import happens inside the function that connects. The module imports
cleanly in an environment that cannot run it, and
`scripts/verify_wheel_importable.py` step 3 now resolves every advertised console script so
the next one cannot ship broken the way that one did (`TASK-039`).

**Constraint:** whatever renders, its heavy import is lazy, its entry point is guarded, and
the engine itself never imports it.

### 1.2 Zero client tests is the documented cause of death

`EPIC-005` §2 D10: *"Zero client tests. All 13 audit tests cover the engine side. Nothing
tests any client, which is how D1–D6 survived."* D1–D6 include "the CLI client can never
connect" and "the client imports a package that does not exist" — defects a single
end-to-end test would have caught on day one, shipped in v2.1.0 and v2.2.0.

**Constraint:** the renderer must be testable *in this repository's existing test harness*,
in CI, on every push. A renderer that can only be verified by a human looking at it is the
same bet that lost last time.

### 1.3 The engine no longer ships QtWidgets base classes

`TASK-038` built `sagittarius_engine/extensions/pyside_mvc/widgets/` — `Surface`, `Panel`,
`Card`, `Overlay`, `StyledButton`, `StyledField`, and two static guards. Commit `7a3ac18`
then removed the whole package from the engine:

> The kit was in the framework on the strength of "reusable", and no second consumer ever
> tested that claim. … 27 commits on this repo, 15 of them (56%) touching `pyside_mvc/`. A
> framework meant to change rarely spent most of a day changing. One real consumer, the
> reference app, in 15 files.
>
> What stays: the MVC bases, the token vocabulary and theme bridge, the QML kit. Those have
> the second consumer this one never had.

**Consequence, and it is the sharpest fact in this ADR:** a graphical client built in this
repository today has exactly one supported widget vocabulary — **the QML kit**. Choosing
QtWidgets would mean re-adding, in `tools/`, the shapes that were deliberately deleted three
days earlier, or hand-rolling `setStyleSheet()` per widget — which is the *"card vs non-card
lộn xộn"* state `TASK-038` was raised to fix. Neither is a decision anyone would defend on
its merits; they are just what happens if the question is never asked out loud.

### 1.4 CI can test Qt. CI cannot test a browser.

`.github/workflows/ci.yml` sets `QT_QPA_PLATFORM: offscreen` globally and runs
`./.github/actions/qt-system-libs` in five jobs (`test`, `architecture`, `examples`,
`benchmark`, `import-guard`). QML screens are already asserted in CI —
`examples/student_management/tests/presentation/roster/test_roster_screen.py` is one.

There is **no** JavaScript, HTML, npm, or browser-automation tooling anywhere in this
repository. The lint gate is ruff + mypy over Python; there is no formatter, type checker,
or test runner that would see a line of client-side JS.

**Consequence:** a Qt client can satisfy §1.2 with the infrastructure that exists. A browser
client would first have to build that infrastructure, and until it did, it would be an
untested client — §1.2 exactly.

### 1.5 The observed process is usually a desktop app on the same machine

Both real consumers — `examples/student_management` and `Sagittarius_Elite_Warrior` — are
PySide6 desktop applications. The "attach to a headless container over the network" case is
supported by the transport (`ADR-001` §2.2 keeps token auth and the off-loopback rule) but
is not the common one.

This cuts **against** an argument I would otherwise have made for a browser client on
reachability grounds, and it is recorded here because it changed the recommendation: if the
target were typically a headless server, §2 below would read differently.

---

## 2. Decision

### 2.1 The reference client is a **terminal renderer**, shipped inside `sagittarius-trace`

A `snapshot` subcommand alongside the existing `attach`: connects over the same WebSocket,
requests a snapshot (or subscribes at an interval), and renders plain text — sections for
events, container, lifecycle, tasks, threads, config, and findings.

Stdlib only. No `rich`, no `textual`. (`rich` was already added once as an `audit` extra and
removed by `EPIC-005A` when its only consumer was deleted; re-adding a dependency for
formatting that `str.ljust` does is not warranted.)

**Why this is first, and why it is not a way of avoiding the question:**

1. **It is the only option that makes `ADR-001`'s contract testable the way §1.2 demands.**
   A text renderer's output is a string. `assert "A2" in out` and a golden-file comparison
   are ordinary pytest, in the existing harness, on every push. This is the direct, cheap
   repair for D10.
2. **A text renderer forces the schema to be complete.** Build the graphical client first
   and the schema quietly becomes "whatever the widgets happened to need" — a panel can hide
   a missing field behind a blank space, which is precisely how D3/D4 went unnoticed. Text
   cannot hide a missing field; it prints nothing where something should be.
3. **The entry point, the transport, the auth and the wheel guard already exist.** The
   marginal packaging surface is zero, and `verify_wheel_importable.py` already covers the
   command.
4. **It works where the app is** — over SSH, in a container, on a build agent — without a
   display server, which the graphical client cannot do.

### 2.2 The graphical client is **PySide6 + QML**, using the engine's own kit

When a graphical client is built, it is QML over `sagittarius_engine.extensions.pyside_mvc`,
composing existing kit components (`AppDataTable` for registries and task tables, `LogPanel`
for the findings stream, `StatefulButton`, `BaseCard` derivations) against the token
vocabulary.

Reasons, in order of weight:

1. **It is the only vocabulary the engine still ships** (§1.3). QtWidgets bases left in
   `7a3ac18`; re-deriving them in `tools/` would fork what was just consolidated.
2. **It gives the QML kit the second consumer that `7a3ac18` says a kit needs to earn its
   place.** That commit's whole argument is that a kit with one consumer is not a kit, it is
   an app's internals in the wrong repository. The console is a genuinely different consumer:
   dense tabular data, high update rate, no domain vocabulary — a workload
   `examples/student_management` does not exercise.
3. **`ui-architecture.md`'s guards apply to it for free** — `qml_literal_guard`,
   `raw_primitive_guard`, `gallery_coverage_guard`, offscreen construction with zero QML
   warnings. A client built to that standard is held to it automatically.
4. **CI can run it** (§1.4).

### 2.3 The graphical client is **gated on the terminal client existing first**

Not merely sequenced — gated. The QML client may begin when the snapshot contract is
frozen, the terminal renderer ships, and an end-to-end test exists that starts a real
`TraceServer`, connects, and asserts on rendered output.

This is the anti-D10 mechanism. The failure mode being prevented is specific and has
happened here: pixels arrive, they look convincing, and nobody notices the pipe underneath
them was never tested end to end.

### 2.4 The graphical client lives in `tools/`, behind an extra, with a lazy import

- Package under `tools/`, never under `sagittarius_engine/`. The engine must not gain a UI
  dependency (`EPIC-005` §1, and `ADR-001` §2.10).
- A `dashboard = ["PySide6>=6.5"]` extra. Not a bare dependency.
- `PySide6` imported **inside** `main()`, never at module scope — §1.1's pattern, and the
  literal text of D7.
- Any console script it declares is covered by `verify_wheel_importable.py` step 3, which
  resolves every advertised entry point. `TASK-039` added that guard *because* an entry
  point shipped broken for two releases.

### 2.5 A browser client is **declined for now**, with a stated revisit condition

Not rejected on merit — it is the strongest option on reachability and installs nothing on
the viewer's machine. It is declined because §1.4 makes it the one option that cannot meet
§1.2 without first building a test toolchain this repository does not have, and §1.5 removes
most of the benefit that would justify building one.

**Revisit if:** a consumer needs to inspect a genuinely headless or remote process as its
normal case. At that point the reachability argument outweighs the tooling cost, and this
ADR should be superseded rather than stretched.

---

## 3. The comparison, stated plainly

| | **A. Terminal** | **B. PySide6 + QML** | **C. Browser** | **D. No new client** |
| :--- | :---: | :---: | :---: | :---: |
| Testable in existing CI (§1.2) | ✅ string asserts | ✅ offscreen Qt, 5 jobs | ❌ no toolchain at all | ✅ |
| Keeps the wheel zero-dependency (§1.1) | ✅ stdlib | ⚠️ extra + lazy import | ✅ engine side stdlib | ✅ |
| Uses a vocabulary the engine ships (§1.3) | n/a | ✅ the QML kit | ❌ | n/a |
| Works with no display server | ✅ | ❌ | ⚠️ needs a browser somewhere | ✅ |
| Reads dense tables comfortably | ⚠️ | ✅ `AppDataTable` | ✅ | ❌ |
| Answers the actual request (§1.1 of ADR-001) | ⚠️ partially | ✅ | ✅ | ❌ cannot attach to a running process |
| New surface to build and maintain | small | medium | **large** (a second toolchain) | none |

**D is rejected outright**: `sagittarius-doctor` boots the app, prints, and exits. It cannot
attach to an already-running process, which is the whole request.

---

## 4. Consequences

### Accepted

- **The first thing delivered will not look like a dashboard.** It is a text report. Anyone
  expecting panels from milestone one will be disappointed, and that expectation should be
  set now rather than managed later.
- **The graphical client is deferred, and deferred work sometimes never happens.** Mitigated
  by the terminal client being genuinely useful on its own — over SSH and in CI it is the
  *better* of the two — rather than scaffolding that only pays off if phase two lands.
- **A `dashboard` extra is a supported install path** the release process must then cover.
- **QML is chosen while its consumer base is narrowing.** `Sagittarius_Elite_Warrior` dropped
  QML project-wide (`TASK-038`, that repo's `EPIC-006`), so the kit's remaining evidence of
  reuse is `examples/student_management`. This is the weakest point in §2.2 and is recorded
  as such: the console would *strengthen* the kit's second-consumer claim, but if the QML kit
  is itself retired, §2.2 must be superseded rather than quietly reinterpreted.

### Gained

- Both renderers consume the same imported contract (`ADR-001` §2.3), so a schema change
  breaks the terminal client's tests in CI before it can reach a panel and go silently blank.
- The terminal client is usable from a build agent, which makes "dump the app's wiring state
  when an integration test fails" available for free.

---

## 5. Open questions, deliberately not decided here

1. **Refresh rate and whether the terminal client redraws in place** (a full-screen TUI) or
   prints successive reports. Full-screen redraw is where a `textual`/`rich` dependency would
   start being argued for; the decision is deferred until the plain version exists and its
   limits are felt rather than predicted.
2. **Whether the QML client reuses `examples/student_management`'s shell or gets its own.**
   Depends on `EPIC-001D`'s runtime region work landing first.
3. **Whether findings are rendered client-side from raw state, or the engine sends
   `Finding`s.** `ADR-001` §2.3 implies the latter (one schema, imported) but does not settle
   it; it is a real choice with a cost either way and belongs in the implementation spec.
