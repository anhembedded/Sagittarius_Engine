# Reference: external UX/UI handoff for the runtime state console

Received 2026-09-09, produced by a separate design AI from the functional feature brief this
repository handed it (`EPIC-007`'s feature set, described functionally — no UI constraints —
then corrected twice: to require an interactive prototype rather than a static mockup, and to
add the socket-address "Connecting to a backend" flow this document's §5 answers).

**What this file is:** the design AI's own handoff markdown, saved verbatim so it survives
past the chat session that received it. **What this file is not:** the actual design
artifacts. The handoff names five source files (two `.dc.html` interactive prototypes, a
PySide/Qt implementation spec, a mock data engine `console-data.js`, and a design-system
stylesheet) plus five reference screenshots (Overview/reading, Events & wiring, the connect
flow, and two Not-attached/stale renderings) shown inline in that chat session — **none of
those source files or images are attached to this repository**. `EPIC-008A` re-derives the
token and component decisions this document implies by reading it, not by opening the
original `.dc.html` files, which this repo does not have access to. If the original prototype
files become available later, place them under this `reference/` directory alongside this
file rather than losing them a second time.

---

# Handoff: Runtime State Console

> Written to be implemented by someone — or something — that was not in the design
> conversation. Read this file top to bottom; it is self-sufficient. The HTML in this
> folder is the reference rendering, not the deliverable.

---

## 1. Overview

A desktop diagnostic tool that attaches to **one** running backend process at a time over a
socket and shows what that process looks like **right now**: what is wired, what is
registered, what is alive, and what looks wrong about that.

- The backend pushes a **full snapshot** of its own state roughly **once per second**.
- Nothing in the tool is historical. There are no charts over time, no log tail, no scrubber.
  Every number is "as of the latest snapshot".
- The tool is **read-only**. It never writes to the backend. Exactly one write-shaped control
  exists anywhere in the UI (*Reprocess*, in Signals) and it is **permanently disabled on
  purpose**, with the reason printed next to it.
- Audience: a developer or operator debugging a live process, usually with a terminal and logs
  open beside this window. Density and legibility of real data matter more than decoration.

All data in the prototype is **simulated** (see `console-data.js`). No network code exists.

---

## 2. About the design files

| File | What it is |
| --- | --- |
| `Runtime Console A - Rail.dc.html` | **The design to build.** Working interactive prototype: rail + per-section sub-tabs, light/dark themes, full connect flow, all connection states, all five sections. |
| `Runtime Console B - Inspector.dc.html` | An **alternate structural take** kept for reference: rail-as-tree + master/detail inspector, dark rail, bottom status bar. Not the primary target. Useful if you need a right-hand detail pane. |
| `Runtime Console A - PySide Spec.dc.html` | Qt/PySide6 implementation spec: token dictionary with resolved hex, widget map, QSS template, refresh rules, list of CSS features QSS lacks. **Read this if the target is Qt.** |
| `console-data.js` | The mock snapshot engine. Pure function of `(flags, tick)` → a full snapshot object. This doubles as the **data contract**. |
| `_ds/industry-…/styles.css` | The design system stylesheet (tokens + component classes) the prototype loads. |
| `_ds/industry-…/readme.md` | The design system's own guide (visual grammar: blueprint frames, type, colour rules). |
| `support.js`, `macos-window.jsx` | Runtime + window-chrome helper needed to open the HTML locally. Not part of the product. |

**These are design references written in HTML.** Do not ship them and do not port the HTML
structure literally. Recreate the design in the target codebase's own environment (Qt/PySide,
React, SwiftUI, WinUI…) with that environment's idiomatic widgets, layout system and state
management. If there is no existing environment, pick one appropriate for a desktop
diagnostic tool and implement there.

To open the references locally, serve the folder over HTTP (`python3 -m http.server`) and open
`Runtime Console A - Rail.dc.html` — the files load `support.js` and the stylesheet by
relative path, so `file://` will not work.

**Fidelity: high.** Colours, type, spacing, density, copy, states and interactions are final.
Recreate them faithfully. Where the target platform cannot express something (CSS filters,
hatch gradients, sticky headers) the PySide spec lists the substitution; apply the same
reasoning for other platforms.

---

## 3. Data contract — the snapshot

One message type. Field names below are the contract; `console-data.js::buildSnapshot`
produces exactly this shape.

```
Snapshot {
  clock: "11:47:05"                 // wall clock of the snapshot, host-side
  lifecycle {
    phase: "Running"                // one of phases[]
    phases: ["Constructing","Configuring","Modules loading","Wiring","Running"]
    phaseIndex: 4                   // index into phases[]
    uptime: 15128                   // seconds
    modules: [{ name: "Ingest", ready: true }, …]
    modulesReady: 12                // count of ready
    modulesRegistered: 12           // total registered
  }
  pools: [{                         // worker / thread pools
    name: "ingest-io", inFlight: 6, max: 16, queued: 3,
    submitted: 148302, completed: 148296
  }, …]
  events: [{                        // every event type the bus knows about
    name: "parcel.scanned", by: "Yard" | null, handlers: 6,
    emitted: 88402, failures: 11,
    declared: true,                 // false = nothing ever declared this name
    subscriber: "BillingProjectionHandler",   // only when declared == false
    near: "shipment.arrived"                  // nearest declared name (typo hint)
  }, …]
  undeclaredCount: 2                // convenience count of declared == false
  container {
    openScopes: 43                  // currently open DI scopes
    scopePeak: 43
    built: 11                       // registrations with an instance
    registrations: [{ abs: "IParcelRepository", impl: "SqlParcelRepository",
                      life: "Singleton" | "Scoped" | "Transient", built: true }, …]
  }
  tasks: [{                         // tracked background tasks
    id: "tsk-8841", name: "reindex-parcels", owner: "Yard",
    state: "Running" | "Completed" | "Pending" | "Failed",
    progress: 62,                   // percent
    elapsed: 252,                   // seconds
    errorType: "TimeoutException",  // Failed only
    error: "…", stack: ["at …", …]  // Failed only
  }, …]
  limits {
    tasksRetained: 128, tasksMax: 256,
    schedulerJobs: 5, schedulerPaused: 1, schedulerBroken: 1,
    jobs: [{ name, trigger, next: string|null, state: "Waiting"|"Paused"|"Broken" }, …]
  }
  deadLetters: [{                   // exhausted retries, set aside
    id: "dl-4417", event: "parcel.scanned", handler: "YardTelemetryHandler",
    errorType: "SqlException", message: "…", payload: "{ … }",
    retries: 5, ago: 214            // seconds since set aside
  }, …]
  machines: [{                      // state machines the backend was told to watch
    name: "ShipmentFlow", key: "WB-40912", state: "AtCustoms",
    states: ["Created","Manifested",…],   // declared states, in order
    attempts: 11, rejections: 3,
    log: [{ from, to, ok: bool, ago: seconds, reason: "…" /* !ok only */ }, …]
  }, …]
  uiThread: {                       // ONLY when the backend is a desktop app
    freezes: 2, longestFreezeMs: 1842, crossThreadTouches: 1
  } | null                          // null = headless host, section must be ABSENT
}
```

**Derived signal counts** (`console-data.js::signalCount`) drive the rail badges:

```
events    = undeclaredCount
container = openScopes > 24 ? 1 : 0
tasks     = tasks.filter(state == "Failed").length + limits.schedulerBroken
signals   = deadLetters.length + sum(machines[].rejections)
total     = sum of the above
```

`uiThread == null` must remove the **UI thread** sub-tab entirely — not show it empty or
zeroed. A zero in that section means "watched, and clean"; absence means "not measured".

---

## 4. Connection state machine

This is the spine of the design. The user must never be unsure which state they are in.

| State | Meaning | Has snapshot? |
| --- | --- | --- |
| `COLD` | No target attached this session. | no  |
| `CONNECTING` | Socket opening, handshake pending. | no  |
| `FAILED` | An attempt failed. Carries an error kind + code. | no (never had one) |
| `IDLE` | Attached; waiting for the first snapshot. | no  |
| `READING` | Attached and receiving. The healthy state. | yes, live |
| `STALE` | Was reading; connection dropped. Last snapshot retained. | yes, frozen |

Transitions:

```
COLD ──connect(addr)──▶ CONNECTING ──ok(≈1.5s)──▶ IDLE ──first snapshot(≈3s)──▶ READING
  ▲                        │  │                                                   │
  │                     cancel │ fail                                       detach │ drop
  └────────────────────────┘  ▼                                                   ▼
                            FAILED ──retry / connect(other)──▶ CONNECTING      STALE
                                                                                  │
                                                            reconnect ───────────┘
```

Rules that are requirements, not styling:

1. **`FAILED` and `STALE` are different messages and must read as different messages.**
   `FAILED` = "the attempt did not succeed, there is no data, here is the errno".
   `STALE` = "this data was real, it is now frozen, here is how old it is and why it stopped".
   Never fold a failed attempt into a generic "Not attached".
2. **An empty table must never be reachable in a non-`READING` state.** Each section renders
   one of: attach view (`COLD`/`FAILED`), connecting plate, idle plate, data (`READING`), or
   data + stale banner (`STALE`). The calm "confirmed empty" plate lives *inside* the data
   view, so "empty" always means "confirmed empty right now, at `clock`".
3. **`STALE` freezes everything except the staleness clock.** Data at `opacity: .55`, a
   hatched fault banner above it, and a "stale for MM:SS" counter that keeps ticking.
4. Switching sections never affects the connection.

### Status band (always visible, top of the app)

Left → right: a 5px full-height stripe in the state colour · state dot (animated) · state
name + note · heartbeat ribbon (44 ticks, one per received snapshot; flat dotted line when
not reading) · age block (label / value / `snapshot HH:MM:SS`) · target address + `change…`
link · primary button.

State-dependent text (exact copy):

| State | Name | Note | Age label / value | Button |
| --- | --- | --- | --- | --- |
| `READING` | Attached · reading | snapshot stream live · ~1/s | last snapshot / `00:01 ago` | Detach |
| `IDLE` | Attached · idle | handshake complete · no snapshot yet | waiting for / `MM:SS` | Detach |
| `CONNECTING` | Connecting | opening socket · `<addr>` | elapsed / `MM:SS` | Cancel |
| `FAILED` | Connection failed | `<error title lowercased>` · `<code>` | last attempt / `failed` | Retry |
| `STALE` | Not attached | showing last-known data | stale for / `MM:SS` | Reconnect |
| `COLD` | Not attached | no target attached | last contact / `never` | Attach… |

Stripe/dot/name colour: `accent` in `READING`; `accent-700` in `IDLE`/`CONNECTING`; `fault`
in `FAILED`/`STALE`/`COLD`.

---

## 5. Connect flow

### Address entry

- **One field** holds the whole target: `ws://host:port` or `wss://host:port?token=…`.
  No separate host / port / token inputs — they drift apart in practice.
- Enter in the field, or the primary button, starts the attempt.
- Button label: `Connect` (cold/failed) · `Connect instead` (already attached) · `Retry` (after
  a failure).
- Helper copy under the field, verbatim:

  > `ws://host:port` for a local or trusted host, `wss://host:port?token=…` where the backend
  > requires a console token. The address is the whole target — there is no separate host, port
  > or credential field to keep in sync.

### Recent addresses

Five most recent, most-recent-first, persisted between runs. Each row: address (monospace,
elided if long), `process · when last used`, and a right-aligned button reading `connect`, or
`attached` (accent-outlined, for the current target). A successful connect moves that address
to the top with "just now".

### Changing target while attached

`change…` next to the target in the status band opens the same attach view over the section
body (`cancel` returns to the data). It shows, verbatim:

> Currently attached to `<addr>`. Connecting somewhere else drops this connection first; the
> tool does not hold two at a time.

### Validation and failure kinds

Validation regex used by the prototype:
`/^wss?:\/\/[^\s/:]+:\d{2,5}([/?][^\s]*)?$/`

| Kind | Trigger (prototype rule) | Title | Code | Detail |
| --- | --- | --- | --- | --- |
| `malformed` | fails the regex — **no socket is opened** | Address is not valid | `EINVAL` | Expected `ws://host:port` or `wss://host:port?token=…` — got "`<addr>`". No connection was attempted. |
| `refused` | port `9999` or `0` | Connection refused | `ECONNREFUSED` | Nothing accepted the socket at `<addr>`. The address parsed fine; there is simply no listener on that port. |
| `rejected` | `wss://` without `token=` | Rejected by the backend | `HTTP 401` | The snapshot endpoint answered and refused the handshake: the console token was missing or wrong. |

In a real build map the transport's own errors onto these three kinds (refused / host not
found → `refused`; auth close code → `rejected`; URL parse failure → `malformed`).

The failure plate shows: `ATTEMPT FAILED` stamp + code · title in fault · the address in
monospace · the detail sentence · a **Worth checking** list of 3 concrete checks · a `Retry`
button · and this sentence, verbatim:

> This is a failed attempt, not a dropped connection — no snapshot was ever received from this
> address, so there is no last-known data to show.

"Worth checking" lists:

- **refused** — Is the process actually running on that host? / Does the port match the host's
  `--console-port`? / A remote host needs `--console-bind 0.0.0.0`; the default is loopback only.
- **malformed** — Include the scheme: `ws://` or `wss://` / Include the port, e.g. `:8781` /
  Paste the whole address, with no spaces.
- **rejected** — Append `?token=…` to the address / The token is written to `console.token` in
  the host's run directory / `wss://` targets always require one.

---

## 6. Shell layout

```
┌ window ─────────────────────────────────────────────────────────────────┐
│ title strip 38px            (OS chrome in a real app — see §11)         │
├─────────────────────────────────────────────────────────────────────────┤
│ ▌ status band  ~62px   (5px state stripe + state + ribbon + age + …)    │
├─ stale banner (STALE only) ~38px ───────────────────────────────────────┤
│ rail 218px │ section header (kicker, title, meta, sub-tabs)             │
│  fixed     ├─────────────────────────────────────────────────────────── │
│            │ section body — the only scrolling region                   │
│            │ padding 20px 22px 44px                                     │
├─ simulator drawer (dev builds only, collapsible) ───────────────────────┤
└─────────────────────────────────────────────────────────────────────────┘
window: min-width 880px (comfortable from 1180), min-height 600px, height min(880px, 90vh)
```

**Rail** — `SECTIONS` label; five rows, 36px tall, `01`–`05` index in mono at 45% ink, label in
Barlow Condensed 600 / 14px; active row: `accent-200` fill, 3px `accent` left border,
`accent-900` text; hover `ink @ 6%`. A fault badge (mono 10px, `fault-fill` bg, `on-fault`
text, 3px 5px) appears on the right of a row when that section's signal count > 0.

Rail footer: **Appearance** row with a light/dark segmented control, then **Target** —
process name, `pid … · host`, runtime, `build …` — then: "Read-only. This tool never writes to
the attached process."

**Section header** — kicker `SECTION 0N` in `accent-700` 9px/.16em uppercase; title 30px
Barlow Condensed 600; right-aligned meta line in mono 12px at 50% ink; sub-tab row below with
a 1px bottom rule, active tab: `accent` 2px underline + `accent-900` text, inactive 50% ink,
each tab shows a count in mono at 60% opacity.

---

## 7. Sections

Sub-tabs per section (label — count shown in the tab):

1. **Overview** — Status · Modules (12)
2. **Events & wiring** — All (15) · Undeclared (2) · With failures (4) · Never emitted (1)
3. **Container** — Registrations (15) · Never built (4) · Open scopes (43)
4. **Tasks & threads** — Tasks (5) · Thread pools (4) · Limits
5. **Signals** — Dead letters (3) · Watched machines (2) · UI thread *(only if `uiThread`)*

### 7.1 Overview → Status

Three equal plates in a row (`1fr 1fr 1fr`, gap 26px), then a full-width pools table.

- **Connection** — kicker; state name at 32px in the state colour; then mono 12px lines:
  state note / `<age label> <age value>` / `snapshots received N`.
- **Lifecycle** — phase at 32px; a 5-segment progress strip (segments ≤ `phaseIndex` in
  `accent`, rest `ink @ 18%`); `12/12 modules initialized · uptime 4h 12m`; then a 12-cell
  grid of 11px module squares — filled `accent` when ready, hairline outline when not, each
  with a tooltip `"<name> · ready|initializing"`.
- **Signals** — kicker and figure turn `fault` when `total > 0`; figure reads `N open` or
  `All clear`; then four rows `count · label · →`, each a button that jumps to the offending
  section+sub-tab: undeclared event names → Events/Undeclared · scope leak suspected →
  Container/Open scopes · failed tasks / broken jobs → Tasks/Tasks · dead letters +
  rejections → Signals/Dead letters. Zero rows are muted, not hidden.
- **Worker pools table** — `pool · occupancy · in flight · max · queued · submitted ·
  completed`. Occupancy is a 9px hairline-bordered bar plus a `NN%` label; bar and in-flight
  value turn `fault` at 100%; queued turns `fault` above 20. Heading `Worker pools` with
  `N threads in flight · N queued` beside it.

### 7.2 Overview → Modules

Table `# · module · state · init`, max-width 760px. State is a tag: `initialized`
(`accent-100` bg / `accent-800` text) or `initializing` (transparent / `fault`).

### 7.3 Events & wiring

When any undeclared name exists and the tab is All or Undeclared, a banner above the table:
`WIRING BUG` stamp + copy, verbatim:

> `N` subscriptions point at names that were never declared: `<names>`. No module ever declared
> these names, so nothing will ever emit them. The subscription is legal, silent, and dead — no
> error, no log line, just a handler that never runs.

Table, all headers sortable (click toggles asc/desc, indicator `↑`/`↓`; default sort
`emitted` desc): `event · declared by · handlers · emitted · failed · declaration`.

- Undeclared row: 3px `fault` left border, 45° hatch background (`fault @ 7%`), name in
  `fault`, `declared by` reads `—` in fault, and a second line under the name in 11px:
  `subscribed by <subscriber> · never declared · did you mean <near>?`
- `failed` count in `fault` when non-zero, else muted. `emitted` muted when 0.
- `declaration` tag: `declared` (transparent, `accent-400` border, `accent-800` text) or
  `undeclared` (`fault-fill` bg, `on-fault` text).
- Empty filter → calm plate, e.g. "Every subscribed name is declared" +
  "Confirmed by the snapshot at `HH:MM:SS` — this filter matches nothing right now."

### 7.4 Container

- **Registrations / Never built** — sortable table `abstraction · implementation · lifetime ·
  instance`. Lifetime is an outlined tag (`accent-500` border for Singleton, `accent-400` for
  Scoped, neutral for Transient). Instance reads `instance built` or `never resolved` (muted).
- **Open scopes** — two columns (`330px` plate + table). Plate: `Open scopes` kicker, count at
  46px, both in `fault` when > 24; note line `climbing since attach · none closed` or
  `steady · opened and closed with each request`; then: "A scope should close when the unit of
  work that opened it ends. A count that only climbs means something is holding one open."
  Table `scope · age · resolved in this scope`, oldest 6, rows in `fault` when leaking.
  Footnote states how many of N are shown and what the ages mean.

### 7.5 Tasks & threads

- **Tasks** — sortable `task · state · progress · elapsed · owner`. Task cell shows name +
  `id` beneath. State tag: Running (`accent-200`/`accent-900`), Completed/Pending (outlined
  neutral), Failed (`fault-fill`/`on-fault`). Progress is the same bar as pools; failed bars
  are `fault`, completed `accent-400`. **A failed row is clickable and expands** a detail block
  beneath it: error type in fault caps, the message, then the stack lines in mono 12px, inside
  a `fault @ 5%` panel with a 3px `fault` left border. Footnote: "Click the failed row to read
  its exception and stack."
  Empty → "No tracked tasks" / "The registry is empty and holding 0 of 256 slots. Confirmed by
  the snapshot at `HH:MM:SS`: the backend has nothing running in the background right now."
- **Thread pools** — the pools table plus an `outstanding` column (`submitted − completed`).
- **Limits** — two plates (`1fr 1fr`) then a full-width jobs table.
  *Task registry*: `128 / 256` at 42px + a bar + explanation of the cap.
  *Scheduler*: three figures — jobs / paused / broken — broken in `fault`, then: "Broken means
  the job is still registered but has no next fire time — it will never run again and nothing
  will say so."
  Jobs table `job · trigger · next fire · state`; a broken job shows `none — dead` and the tag
  `no next fire`.

### 7.6 Signals

- **Dead letters** — one blueprint card per entry, max-width 1000px, `fault`-tinted border.
  Header row: `dl-4417` in fault mono · event name at 19px · right-aligned `set aside 3m 34s
  ago` / `after 5 retries`. Then two labelled fields (`failing handler`, `error` in fault),
  the message in prose, the payload in a dashed-border mono block, and finally the disabled
  action row:
  `[ Reprocess ]` (disabled, 45% opacity, `not-allowed` cursor) followed verbatim by:

  > Disabled by design: replaying a dead letter writes to the attached process. This console is
  > strictly read-only, so the action is shown but never armed.

  Empty → a plate with a `+` registration mark, "Dead-letter queue empty", and: "Nothing has
  exhausted its retries in the `MM:SS` since attach. This is a live confirmation from the
  snapshot at `HH:MM:SS`, not an absence of data."

- **Watched machines** — one plate per machine: `watched machine` kicker, `Name` + `key` in
  mono, `current state · X`; right-aligned pair of figures `attempts` and `rejected`
  (rejected in `fault` when > 0 — it is a first-class number, never something the user counts).
  Then the declared states as a chip row with the current state filled `accent`. Then the
  transition log, newest first: `age · ACCEPTED|REJECTED · from → to · reason`. Rejected rows
  are hatched, fault-inked, and carry the rejection reason right-aligned in the row.
  Empty → "Nothing being watched" / "The backend reports no state machines under observation.
  Machines are opt-in by name on the host side — this is a healthy, deliberate zero, confirmed
  at `HH:MM:SS`."

- **UI thread** — three plates (`1fr 1fr 1fr`): `UI thread freezes` (`dispatcher stalls >
  250ms`), `Longest freeze` (`single worst stall`), `Cross-thread touches` (`UI mutated off the
  dispatcher`), figures at 46px, fault when non-zero. Footnote when clean: "Measured since
  attach, and clean: zero here means watched and healthy, not unmeasured. A headless host would
  not show this tab at all."

---

## 8. Interactions

| Interaction | Behaviour |
| --- | --- |
| Section switch | Rail click → swaps the body; sub-tab selection is remembered per section; connection untouched. |
| Sub-tabs | Filter or panel switch within the section. Counts live-update. |
| Sort | Click a header cell; same key toggles direction; text sorts asc first, numbers desc first; indicator `↑`/`↓` in the header. Sort survives snapshot updates. |
| Expand | Failed task rows expand inline (one at a time). Nothing else expands. |
| Jump | Overview → Signals plate rows jump to the section **and** sub-tab that shows the problem. |
| Live update | Every visible number refreshes on each snapshot (~1s) with no user action, and **without** losing scroll position, sort, selection or expansion. |
| Hover | Rows: `ink @ 4%`. Rail: `ink @ 6%`. Buttons: accent tint / accent fill when pressed. |
| Focus | 2px `accent` outline, 2px offset (from the design system). Never a browser default ring. |
| Disabled | 45% opacity, `not-allowed`. Only ever *Reprocess*. |

Animations (all cheap, all optional-but-nice):

| Name | Spec |
| --- | --- |
| state dot pulse | opacity 1 → .25 → 1; 1s (`READING`), 1.6s (`IDLE`), .7s (`CONNECTING`); none otherwise |
| caret blink | step-end 1.1s on the `_` after "awaiting first snapshot" |
| idle shimmer | a 22%-wide accent-tinted gradient sweeping left→right across skeleton rows, 1.8s linear infinite |
| heartbeat | one 3px tick appended per snapshot, 44 kept; height 6–26px from activity; last tick full `accent`, older ticks fade to 35%; flat 3px dotted row when not reading |

---

## 9. Application state

```
conn        : COLD | CONNECTING | FAILED | IDLE | READING | STALE
target      : string            // the address currently attached / attempted
addr        : string            // the address entry field's value
recents     : [{ addr, proc, ago }]   // max 5, persisted
failKind    : "refused" | "malformed" | "rejected" | null
snapshot    : Snapshot | null   // last received; retained through STALE
staleFor    : seconds           // ticks while STALE
idleFor     : seconds           // ticks while IDLE
connectFor  : seconds           // ticks while CONNECTING
section     : overview | events | container | tasks | signals
sub         : { <section>: <sub-tab id> }     // remembered per section
sort        : { <table>: { key, dir } }
expandedTask: task id | null
theme       : light | dark
```

Sequencing in the prototype: `CONNECTING` resolves after 2 ticks; `IDLE` advances to `READING`
after 3 ticks. In a real build these are driven by the socket and the first snapshot.

---

## 10. Design tokens

Design system: **Industry** — steel-blue on a light technical ground, Barlow Condensed over
Barlow, square corners, hairline borders, `+` registration marks at the corners of plates.
Cards and figures are transparent line drawings; the primary button is the one solid object.
Full guide in `_ds/industry-…/readme.md`.

### Colour

`--ink` is an RGB triplet used at many alphas: `rgba(var(--ink), α)`. Resolved values are in
the PySide spec §2 for platforms that cannot composite tokens.

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| bg  | `#f2f2f3` | `#151d25` | section ground |
| surface | `#e9e9ea` | `#1c262f` | rail, status band, drawer |
| chrome | `#e7e7ea` | `#232e38` | title strip |
| text / ink | `#1d1f20` (29,31,32) | `#e8ebee` (232,235,238) | ink triplet |
| accent | `#5980a6` | `#94bce3` | live state, bars, selection |
| accent-100…900 | `#eef6ff … #1d2d3d` | reversed | tints, tags, text-on-tint |
| neutral-100…900 | `#f5f5f8 … #2b2b2d` | reversed | chrome, inactive ticks |
| divider | ink @ 16% | `rgba(232,235,238,.22)` | plate borders, rules |
| fault | `#a2402f` | `#e08a76` | fault text, borders, bars |
| fault-fill | `#a2402f` | `#b5452f` | stamps, badges |
| on-fault | `#f2f2f3` | `#fdf1ee` | text on fault-fill |
| fault-text | `#7d3123` | `#f2b8a8` | prose inside fault banners |
| hatch | fault @ 7% | fault @ 10% | 45° repeating diagonal |
| grid-line | `rgba(89,128,166,.13)` | `rgba(148,188,227,.10)` | 26px blueprint grid behind the window |

Ink alphas in use: `.85` primary data · `.7` secondary · `.6` counters · `.5` inert/zero ·
`.45` labels · `.25`/`.22` rules and plate borders · `.16` section rules · `.08`/`.07` row
separators · `.06`/`.04` hover.

Dark mode is the same layout with the accent and neutral ramps **reversed** and the ground
moved to the system's deep steel. Nothing else in the tree knows a theme exists — a single
token dictionary switch.

> Note on colour: the design system is deliberately mono (one steel accent). The brick `fault`
> ink is the one addition, used only for faults — red pencil on a blueprint. Do not add further
> hues.

### Type

| Role | Spec |
| --- | --- |
| Section title | Barlow Condensed 600, 30px, tracking −.01em |
| Plate figure | Barlow Condensed 600, 32–46px |
| Plate/field kicker | Barlow Condensed 600, 9–10px, uppercase, tracking .14–.16em |
| Rail item, tab, button | Barlow Condensed 600, 13–14px, tracking .03–.06em, uppercase for tabs/buttons |
| Table header | Barlow Condensed 600, 10–11px, uppercase, tracking .08–.11em, 50% ink |
| Data cells, addresses, ids | Monospace 13px (`ui-monospace / SF Mono / Menlo`; on Windows prefer JetBrains Mono → Consolas) |
| Sub-lines, footnotes | Barlow 400, 11px, 45% ink |
| Prose | Barlow 400, 13–14px, line-height 1.6 |

### Spacing & density

Table row 34px (padding 8–9px 8–14px), header 30px. Rail row 36px, rail 218px. Plate padding
15px 17px. Grid gap 26px (registration marks need ≥12px clearance). Section body padding
20px 22px 44px. Radius 0 everywhere except the window shell (8px, OS chrome). Borders 1px.

### Contrast

Body-size fault and accent text uses the deep ramp steps (`fault`, `accent-700/800`) — never
the raw accent at 3:1. All data text ≥ 4.5:1 against its ground in both themes.

---

## 11. Platform notes

- **The title strip in the prototype is a stand-in for OS window chrome.** Do not build it.
  Anything it appears to hold (the app title) belongs to the OS; the theme switch and the
  snapshot clock were deliberately moved *into the app* (rail footer and status band) for
  exactly this reason.
- **The simulator drawer is not part of the product.** It exists so every mocked state is
  reachable in the prototype: connection states (`no data`, `stale data`, `idle`, `reading`,
  `connecting…`, `fail: refused`, `fail: malformed`, `fail: rejected`), drop reason (peer
  closed 1006 / unknown), a clock pause, and eight scenario toggles (undeclared event, leaked
  scopes, failed task, dead letters, rejected transitions, desktop host, no tasks, nothing
  watched) plus an `all clear` preset. Ship it behind a `--dev` flag or not at all.
- **Read-only is a product rule, not a limitation to design around.** There are no other
  actions. Do not add refresh buttons (data is push), retry buttons for handlers, or
  clear-queue actions.
- If the target is Qt/PySide6, `Runtime Console A - PySide Spec.dc.html` has the widget map,
  QSS template, refresh rules (`dataChanged`, not `beginResetModel`) and the list of things
  QSS cannot do with the substitution for each.

---

## 12. Assets

None. No images, no icon font, no SVG artwork. Every mark in the design is drawn with borders
and boxes: the registration `+` marks are two 1px lines per corner, the hatch is a 45°
repeating gradient, the "confirmed empty" mark is a `+` built from two divs, the heartbeat is
a row of 3px divs. If icons are wanted later, the design system specifies Lucide at
stroke-width 1.5.

Fonts: **Barlow** and **Barlow Condensed** (Google Fonts, weights 400/500/600/700). Bundle
them rather than assuming a system install. Monospace comes from the platform stack.

---

## 13. Acceptance checklist

- [ ] All five sections reachable at any time; sub-tab selection remembered per section.
- [ ] Six connection states reachable and visually unambiguous; `FAILED` never reads as a
      dropped connection, and `STALE` never reads as live.
- [ ] No section can show an empty table while not `READING`.
- [ ] Each section's empty state names what was confirmed and at what clock time.
- [ ] `uiThread == null` removes the UI-thread sub-tab entirely.
- [ ] Undeclared event names are visually unmissable and name the subscriber + nearest match.
- [ ] Rejected transitions are distinguishable at a glance and the rejection count is a
      first-class figure.
- [ ] Open-scope count turns fault above the leak threshold, with the ages that prove it.
- [ ] Broken scheduler jobs show `none — dead` for next fire.
- [ ] *Reprocess* is present, permanently disabled, with the reason on screen — and is the only
      action in the entire tool.
- [ ] Numbers update ~1/s without disturbing scroll, sort, selection or expansion.
- [ ] Address entry accepts a full `ws://`/`wss://` target, validates before opening a socket,
      keeps 5 recents, and can switch target without restarting.
- [ ] Light and dark themes both pass 4.5:1 on data text.
