# EPIC-007: Runtime State Console

- **Status**: 🟡 **In Progress** — 4/6 subtasks done (`A`, `B`, `C`, `D` shipped 2026-08-27); `E` partially
  shipped the same day — infrastructure and one screen of six, see its own §Progress so far
- **Created**: 2026-08-27
- **Priority**: P2
- **Category**: Observability / Diagnostics / Tooling
- **Decided by**: [`ADR-001`](../../decisions/ADR-001_runtime_state_console_scope_and_transport.md)
  (scope and transport) · [`ADR-002`](../../decisions/ADR-002_state_console_client_ui_framework.md)
  (PySide6 + QML client)
- **Builds on**: `EPIC-005` (trace recorder, transport, protocol) · `EPIC-006` (wiring
  diagnostics, the findings vocabulary) — both are dependencies, neither is modified in
  ways that change their behaviour

> ### ⚠️ Naming collision — read before citing a subtask id
>
> Eight documents in **this** repository already write `EPIC-007A`…`EPIC-007F`, and every
> one of them means `Sagittarius_Elite_Warrior`'s `EPIC-007_chuan_hoa_card_dung_chung`, not
> this epic — see `tokens/defaults.py:46`, `tokens/vocabulary.py:57`, `BUG-004`, `BUG-008`,
> `BUG-009`, `BUG-012`.
>
> This epic takes `007` because [`Tasks/epics/README.md`](../README.md) says the next epic
> takes the highest number in `Tasks/epics/` + 1, and routing around a written rule silently
> is what `design-discipline.md` forbids. The collision is therefore **named** rather than
> avoided: inside this repository, cite this epic's subtasks as `EPIC-007x` and the other
> repository's as **`Elite EPIC-007x`**. A small follow-up task should go back and qualify
> those eight references; it is not folded in here because it touches unrelated files.

---

## 1. What this builds

A tool that attaches to a **running** application built on this engine and shows what is
wired, what is registered, what is alive, and what looks wrong about that — so a red flag is
noticed while the app runs rather than reconstructed from a log afterwards.

Design: <https://claude.ai/code/artifact/29b45155-8fb3-4b54-a6ce-2440f51d8330> — six
artboards, drawn before the decisions were taken, and what `ADR-002` §2.1 is judging.

**It is a state console, not a second timeline.** `ADR-001` §2.1 is the boundary and this
epic does not move it: duration questions stay with `sagittarius-trace` → `.sagtrace` →
Perfetto. A proposal to put a time axis in this tool is a proposal to reverse `EPIC-005` §5
and belongs in an ADR, not in a subtask.

## 2. Why it is mostly assembly, not invention

Roughly 70% of the data already exists as public API. This epic is a collector, a schema, a
transport message, and a client — not a new instrumentation programme.

| Question | Already answered by |
| :--- | :--- |
| declared vs subscribed events, typo'd subscriptions, multi-handler, string-subscribed | `EventRegistry.all()` ⋈ `IEventBus.subscriptions()`; checks **A1 A2 A3 A5** |
| container bindings, abstract vs concrete, unbuildable deps, cycles | `IContainer.registrations()`; checks **C1 C2 C3** |
| handlers that cannot be constructed | checks **B1 B2 B3** |
| extension registered but never initialised; service never started; job that never fires | checks **D1 D2 D3** |
| emitted into the void; handler raised | `RuntimeMonitor`, checks **R1 R2** |
| ring-buffer fill, drops, taps | `TraceRecorder` |
| dead-lettered events | `ResilientEventBus.get_dlq()` — **called by nothing but tests** |
| state-machine transitions, including rejected ones | `BaseStateMachine.add_global_callback()` |

Three things genuinely do not exist and are built here: a task snapshot that includes
finished tasks, thread-pool statistics, and the snapshot schema itself.

## 3. Every milestone runs

This epic's one structural rule, and the reason its subtasks are shaped the way they are:

> **A subtask is not done until there is a command in its own file that a reader can paste
> and watch work.** Not a passing test suite — a command whose *output is the feature*.

`EPIC-005` §2's defect table is the argument. D1 (the CLI could never connect), D6 (the
console script could not start), D7 (it died on a missing import) and D10 (no client tests)
are four separate failures of one kind: nobody ran the thing end to end. Each subtask below
therefore carries a **How to run it** section, and `EPIC-007C` onward those commands attach
to a live process.

## 4. Milestones

| ID | Scope | Runs as | Done when |
| :--- | :--- | :--- | :--- |
| **[A](completed/EPIC-007A_snapshot_contract_protocol_v2.md)** ✅ | Snapshot dataclasses in `contracts.py`; `PROTOCOL_VERSION` 1 → 2 | `pytest tests/extensions/audit/test_snapshot_contract.py` | ✅ **Done 2026-08-27** — 23 tests; masking checks the value as well as the key; a v1 peer is refused naming both versions |
| **[B](completed/EPIC-007B_public_read_apis.md)** ✅ | `ITaskManager.snapshot()`/`pool_stats()`, `IThreadManager.stats()`, `IConfig.sources()`, `IContainer.open_scope_count()`, `ExclusiveAction.held_slot()` | `pytest tests/runtime/tasks/test_task_manager.py -k "snapshot or pool_stats"` | ✅ **Done 2026-08-27** — found and fixed a real deadlock in the process: `.cancel()` on a queued future firing its done-callback synchronously while the caller still held the same lock the callback needed |
| **[C](completed/EPIC-007C_collector_extension_and_snapshot_message.md)** ✅ | `StateConsoleExtension` + `SNAPSHOT` over the existing `TraceServer` | `sagittarius-trace snapshot ws://127.0.0.1:8781` | ✅ **Done 2026-08-27** — found and fixed a real readiness race (`app.stop()` 2.0044s → 0.0031s); one full snapshot measured p50=0.107ms/p95≤0.65ms against a 5ms budget |
| **[D](completed/EPIC-007D_student_management_demo_wiring.md)** ✅ | Demo wiring in `examples/student_management`, incl. seeded faults | `.\examples\student_management\run.ps1 -Console -DemoFaults` | ✅ **Done 2026-08-27** — found and fixed 3 bugs along the way: `WiringInspector`'s D3 check named the wrong attribute, it crashed on any postponed-annotations constructor, and `Scheduler._run()` crashed its own thread on a `next_run=None` job |
| **[E](incomplete/EPIC-007E_qml_client_and_pwsh_runner.md)** 🟡 | `tools/state_console/` QML client + `scripts/run-console.ps1` | `.\scripts\run-console.ps1 -Demo` | 🟡 **Partial 2026-08-27** — `ConsoleConnectionExtension`, packaging, and the Overview screen are real and tested; 4 of 6 screens remain |
| **[F](incomplete/EPIC-007F_signals_dlq_and_state_machines.md)** | Dead-letter queue and state-machine panels | `.\scripts\run-console.ps1 -Demo` | A dead-lettered event and a rejected transition are both visible; neither is visible anywhere today |

**Order: A → B → C → D → E → F.** C is the first milestone that attaches to a live process
and is independently valuable — a text rendering over SSH is a usable tool even if E never
ships. D before E deliberately: a client built against an app with nothing wrong in it will
have every empty state untested, which is `EPIC-005` D1 rebuilt in a new frame.

## 5. Acceptance criteria for the epic

1. **`sagittarius-doctor --strict` still passes in CI** against
   `examples.student_management.doctor_target:build`. The seeded faults of `EPIC-007D` are
   opt-in and are not in that factory's path — see `EPIC-007D` §3, this is the single
   easiest way for this epic to break the build.
2. **Detached cost is unmeasurable.** No timer, no walk, no allocation while no client is
   connected — measured, in the manner of `EPIC-005` §4.2's table, not asserted.
3. **One full snapshot ≤ 5 ms** on `examples/student_management` at ≤ 1 Hz.
4. **No private attribute access** anywhere in the collector — `EPIC-006`'s criterion 2,
   unchanged.
5. **Secrets are masked by default** and cannot be unmasked by a client request.
6. **The client imports the schema**, never redeclares it — a drift is an `ImportError` or a
   type error, not a blank panel (`EPIC-005` D3/D4).
7. **An end-to-end test** starts a real `TraceServer`, connects, and asserts on a parsed
   snapshot. This is the test whose absence let D1–D6 ship twice.
8. **The wheel stays zero-dependency.** `PySide6` reaches the tree only through a `dashboard`
   extra, imported inside `main()`.
9. **Every console script resolves** under `scripts/verify_wheel_importable.py` step 3.
10. **Works on the declared floor** — Python 3.12, per `requires-python`.

## 6. What is deliberately not in this epic

- **A time axis.** `ADR-001` §2.1.
- **Write actions** — reprocessing a dead letter, cancelling a task, firing a job. Every one
  is a write path into a live process from a socket, and that is a security decision with
  its own blast radius. `EPIC-007F` renders the dead-letter queue read-only and shows the
  control disabled; enabling it needs **ADR-003**.
- **Hosted-service liveness.** A service that starts and later dies emits nothing and is
  caught nowhere (`extensions/diagnostics/runtime.py` says so in its own words). The console
  shows *started / not started* and does not imply it knows more. Detecting death is a change
  to the runtime's contract, not a diagnostic, and is its own task.
- **Always-on `tracemalloc`.** `ADR-001` §2.9 — bounded-structure occupancy instead, with
  `tracemalloc` as an on-demand action once write actions exist.
