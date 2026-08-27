# ADR-002: The state console's client is **PySide6 + QML**

- **Status**: 🟠 Proposed
- **Date**: 2026-08-27
- **Category**: Observability / Tooling / Packaging
- **Depends on**: [`ADR-001`](ADR-001_runtime_state_console_scope_and_transport.md) — this ADR
  decides only what *renders* the snapshot that ADR defines
- **Relates to**: `7a3ac18` (QtWidgets kit removed from the engine), `TASK-038`,
  `EPIC-005` §2 D7/D10, `EPIC-001` (UI Engine Foundation), `ui-architecture.md`

> **Decision history.** A first draft of this ADR reached PySide6 + QML by
> elimination: `7a3ac18` had just removed the QtWidgets kit, so QML looked like the only
> vocabulary the engine still shipped, and a terminal renderer was proposed as the first
> client with QML gated behind it. The maintainer then **deliberately widened the field** —
> neither the engine's token palette nor its QML kit was to be treated as binding, and any
> UI framework well-suited to dashboards was in scope. Textual and a browser client were
> weighed on that basis (§3), and PySide6 + QML was chosen anyway.
>
> This document is rewritten to record the decision on its real grounds. The distinction
> matters: a choice made because nothing else was available is fragile — it collapses the
> moment something else becomes available. A choice made with the field open does not.

---

## 1. Context

[`ADR-001`](ADR-001_runtime_state_console_scope_and_transport.md) settles what data leaves
the process and how, and deliberately says nothing about pixels. This ADR answers what
renders it.

Four constraints survive whichever framework wins, and each is written down in this
repository as the outcome of something that went wrong.

### 1.1 The wheel declares zero dependencies — and that is what killed the last client

`pyproject.toml` declares no `[project] dependencies` at all; the only extra is `otel`.
`EPIC-005` §2 D7:

> The wheel is zero-dependency by design, but `tools/audit_dashboard/main.py` imports
> `PySide6.QtWidgets` at module level. A real `pip install sagittarius-engine` therefore
> yields a `sagittarius-audit` command that dies on `ModuleNotFoundError: No module named
> 'PySide6'` before reaching any of its own code.

The pattern that replaced it works and is the precedent to copy: `sagittarius-trace` needs
`websockets`, and neither `extensions/audit/cli.py` nor `infra/trace_server.py` imports it
at module scope — the import happens inside the function that connects. The module imports
cleanly in an environment that cannot run it, and `scripts/verify_wheel_importable.py`
step 3 now resolves every advertised console script so the next one cannot ship broken the
way that one did (`TASK-039`).

**Constraint:** the heavy import is lazy, the entry point is guarded, and the engine itself
never imports the client.

### 1.2 Zero client tests is the documented cause of death

`EPIC-005` §2 D10: *"Zero client tests. All 13 audit tests cover the engine side. Nothing
tests any client, which is how D1–D6 survived."* D1–D6 include "the CLI client can never
connect" and "the client imports a package that does not exist" — defects a single
end-to-end test would have caught on day one, shipped in v2.1.0 and v2.2.0.

**Constraint:** the renderer must be testable in this repository's existing harness, in CI,
on every push.

### 1.3 CI can already test Qt. It cannot test a browser.

`.github/workflows/ci.yml` sets `QT_QPA_PLATFORM: offscreen` globally and runs
`./.github/actions/qt-system-libs` in five jobs (`test`, `architecture`, `examples`,
`benchmark`, `import-guard`). QML screens are already asserted in CI —
`examples/student_management/tests/presentation/roster/test_roster_screen.py` is one.

There is no JavaScript, HTML, npm, or browser-automation tooling anywhere in this
repository. The lint gate is ruff + mypy over Python.

This is the fact that does the most work in §3: it is why a Qt client can satisfy §1.2 with
what exists, and why a browser client would have to build a second toolchain before it
could.

### 1.4 What the engine ships today is the QML kit

`TASK-038` built `pyside_mvc/widgets/` — `Surface`, `Panel`, `Card`, `Overlay`,
`StyledButton`, `StyledField`, and two static guards. Commit `7a3ac18` removed the whole
package from the engine:

> The kit was in the framework on the strength of "reusable", and no second consumer ever
> tested that claim. … One real consumer, the reference app, in 15 files.
>
> What stays: the MVC bases, the token vocabulary and theme bridge, the QML kit.

So a Qt client in this repository composes the QML kit, or it re-derives shapes that were
deliberately removed. That is no longer the *reason* for the decision (§3 weighed
alternatives outside Qt entirely), but it does settle *which* Qt, and it makes QtWidgets a
non-option here rather than a second Qt candidate.

### 1.5 The observed process is usually a desktop app on the same machine

Both real consumers — `examples/student_management` and `Sagittarius_Elite_Warrior` — are
PySide6 desktop applications. Attaching to a headless container over the network is
supported by the transport (`ADR-001` §2.2 keeps token auth and the off-loopback rule) but
is not the common case. Reachability, which would otherwise favour a browser client
strongly, is therefore not the deciding axis.

---

## 2. Decision

### 2.1 The client is PySide6 + QML, composing the engine's own kit

Screens are built from `sagittarius_engine.extensions.pyside_mvc` — `AppDataTable` for the
event, container and task tables; `LogPanel` for the findings stream; `StatefulButton`,
`AppModal`, and `BaseCard` derivations for the rest — against the token vocabulary
(`vocabulary.REQUIRED_COLOUR_TOKENS` plus the spacing/radius/typography/motion defaults).

The reasons, now that nothing forces the answer:

1. **`ui-architecture.md`'s guards apply for free.** `qml_literal_guard`,
   `raw_primitive_guard`, `gallery_coverage_guard`, offscreen construction with zero QML
   warnings. A client built here is held to the engine's own UI standard automatically,
   which no external framework would give.
2. **CI runs it today** (§1.3) — the anti-D10 constraint is satisfiable without new
   infrastructure.
3. **It gives the QML kit the second consumer `7a3ac18` says a kit needs to earn its
   place.** That commit's argument is that a kit with one consumer is an app's internals in
   the wrong repository. The console is a genuinely different consumer: dense tabular data,
   high update rate, no domain vocabulary — a workload `examples/student_management` does
   not exercise. This is now a benefit being deliberately bought, not a side effect.
4. **The team's existing skill is in Qt/QML**, and the tool most likely to be finished is
   the one built in the vocabulary its authors already think in.

### 2.1.1 The screens this decision is about

A six-artboard mockup of the console — overview, events &amp; wiring, tasks &amp; threads, a
text rendering, signals (dead-letter queue and state machines), and the not-attached state —
was drawn against the engine's token vocabulary before this decision was taken, and is what
§2.1 is judging:
<https://claude.ai/code/artifact/29b45155-8fb3-4b54-a6ce-2440f51d8330>

It is information architecture, not a build target: no QML was written for it, and the
layouts are what the kit must be able to express, not a promise about how it will.

### 2.2 The palette is the engine's token vocabulary, and the console supplies its own values

`ui-architecture.md` §2.1 already draws this line: the engine defines token **names**, the
consumer supplies **values**. The console is a consumer, so it supplies its own palette dict
filling the 11 required colour tokens, and binds `Theme.<name>` exclusively — no literal
colour, spacing, radius or duration in its QML.

It does **not** inherit `examples/student_management`'s palette. That palette exists to make
the sample app read as its own thing; a diagnostic console that looked like one of the apps
it inspects would be actively confusing when both are on screen.

### 2.3 The contract is proven end to end before any screen is built

The earlier draft gated QML behind a full terminal client shipping first. That gate is
**dropped** — its premise was that a GUI could not be tested here, and §1.3 shows that is
false in this repository.

What survives is the part that was actually load-bearing:

- The snapshot dataclasses in `contracts.py` are frozen (in the API sense) before screen
  work starts.
- An end-to-end test starts a real `TraceServer`, connects a client, and asserts on a
  parsed snapshot — the test D1–D6 would have failed on immediately.
- A **plain-text renderer exists as part of that test**, not as a shipped product
  milestone: `python -m ... --format text` printing the snapshot. It costs almost nothing,
  it keeps schema completeness honest (a panel can hide a missing field behind blank space;
  a text dump cannot), and it makes the console usable over SSH for free.

If that text renderer turns out to be wanted as a product surface, it is a `snapshot`
subcommand on `sagittarius-trace` and needs no ADR.

### 2.4 The client lives in `tools/`, behind an extra, with a lazy import

- Package under `tools/`, never under `sagittarius_engine/`. The engine must not gain a UI
  dependency (`EPIC-005` §1, `ADR-001` §2.10).
- A `dashboard = ["PySide6>=6.5"]` extra. Not a bare dependency.
- `PySide6` imported **inside** `main()`, never at module scope — §1.1's pattern, and the
  literal text of D7.
- Any console script it declares is covered by `verify_wheel_importable.py` step 3.

### 2.5 The console is a separate process, always

Restating `ADR-001` §2.10 because this decision makes it tempting to break: the observed app
is a Qt app and the console is now also a Qt app, so embedding the console into the app it
observes becomes one import away. It forfeits all three properties the two-process split
exists for — surviving the app it observes, attaching to an already-running process, and
adding no UI dependency to the engine.

---

## 3. The alternatives, weighed with the field open

| | **PySide6 + QML** | **Textual (Python TUI)** | **Browser (vanilla JS)** | **QtWidgets** |
| :--- | :---: | :---: | :---: | :---: |
| Testable in existing CI (§1.2) | ✅ offscreen Qt, 5 jobs | ✅ `pytest-textual-snapshot` | ❌ no toolchain at all | ✅ |
| Keeps the wheel zero-dependency (§1.1) | ⚠️ extra + lazy import | ⚠️ extra | ✅ engine side stdlib | ⚠️ extra |
| Uses a vocabulary the engine ships (§1.4) | ✅ the QML kit | ❌ | ❌ | ❌ removed by `7a3ac18` |
| Works with no display server | ❌ | ✅ terminal **and** browser via `textual serve` | ⚠️ needs a browser somewhere | ❌ |
| Dense tables, high refresh | ✅ `AppDataTable` | ✅ `DataTable` | ✅ | ✅ |
| Second toolchain to maintain | no | no | **yes** | no |
| Team fluency | **high** | low | low | medium |

**Textual was the serious contender** and is recorded as such. It collapses terminal and
browser into one Python codebase, its snapshot testing is a stronger anti-D10 mechanism than
anything proposed here, and it needs no display server. It lost on two counts: it shares
nothing with the engine's own UI standard, so none of `ui-architecture.md`'s guards apply to
it and the console would drift into a second visual vocabulary maintained by the same
people; and §1.5 removes most of the headless advantage that is its strongest card.

**A browser client** is the best dashboard ecosystem in the abstract and installs nothing on
the viewer's machine. It lost on §1.3 alone: it is the one option that cannot meet §1.2
without first building a JS test toolchain this repository does not have, and D10 says an
untested client is a dead client.

**QtWidgets** is not a live option here (§1.4).

**Revisit** the browser option if a consumer needs to inspect a genuinely headless or remote
process as its normal case; at that point §1.5 no longer holds and this ADR should be
superseded rather than stretched.

---

## 4. Consequences

### Accepted

- **QML is chosen while its consumer base is narrowing.** `Sagittarius_Elite_Warrior`
  dropped QML project-wide (`TASK-038`, that repo's `EPIC-006`), so the kit's remaining
  evidence of reuse is `examples/student_management` — and now this console. This is the
  weakest point in §2.1 and is recorded plainly: the console is being asked to carry part of
  the kit's justification, which means a decision to retire the QML kit is also a decision
  about this console. If that happens, §2.1 must be **superseded**, not reinterpreted.
- **A `dashboard` extra is a supported install path** the release process must cover.
- **The console needs a display server**, so it cannot inspect a headless target. Accepted
  on §1.5; the text renderer from §2.3 is the fallback for the cases that do arise.
- **Kit gaps will surface.** The console's workload (dense tables, sparklines, state-graph
  nodes, severity chips) is not what the kit was measured against. Expect §1.1 escape
  hatches in `ui-architecture.md`; a repeated escape is a signal to promote the shape into
  the kit, per that rule, not to keep re-deriving it.

### Gained

- The console and any later renderer consume the same imported contract (`ADR-001` §2.3),
  so a schema change breaks a test in CI before it can reach a panel and go silently blank.
- The QML kit gets exercised by a consumer with no domain vocabulary — the cleanest possible
  test of whether it is a design system or one app's internals.

---

## 5. Open questions, deliberately not decided here

1. **Whether the console reuses `examples/student_management`'s shell or gets its own.**
   Depends on `EPIC-001D`'s runtime region work landing first.
2. **Whether findings are rendered client-side from raw state, or the engine sends
   `Finding`s.** `ADR-001` §2.3 implies the latter (one schema, imported) but does not settle
   it; it is a real choice with a cost either way and belongs in the implementation spec.
3. **Whether the text renderer of §2.3 becomes a shipped `sagittarius-trace snapshot`
   subcommand.** No ADR needed either way.
