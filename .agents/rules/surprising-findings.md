---
trigger: always_on
---

# Rules: Report Anything Counter-Intuitive

> Context: the user makes the architecture decisions in this repository. A
> surprise that stays in the agent's head — or gets buried in a commit
> message nobody re-reads — is a decision they were never given the chance
> to make.

---

## The obligation

**When something turns out to work differently than a competent engineer
would reasonably expect, say so explicitly, in the reply, at the moment it
is found.** Not only in the commit message. Not only in a task file. Those
are the permanent record; the reply is what actually reaches the user in
time to change a decision.

This applies whether or not the surprise was a problem, whether or not it
is already fixed, and whether or not it was the agent's own mistake.

## What counts as counter-intuitive

Not "anything mildly interesting" — that turns the signal into noise. The
test is: **would a competent engineer have predicted this, and would being
wrong about it cost them?** Every example below is real, from this
repository, on 2026-08-23.

| Category | Real example |
| :--- | :--- |
| **Success indicators that lie** | `--show` mode: process alive, `isVisible()` true, valid window handle, correct geometry — and nothing on screen. The platform was `offscreen`, forced at module import before argv was read. |
| **A test suite that stays green while the feature is broken** | Four tests passed while every card's compact badge rendered blank. `QQuickWidget.errors()` reports *parse* errors only; a binding that throws at evaluation is a runtime warning it never sees. |
| **A tool that does the opposite of its name at the edges** | A `default property alias` swallows the component's **own** internal children, not just a consumer's — redirecting them into the very container being declared. |
| **The obvious approach failing for non-obvious reasons** | Embedding a Python `QObject` in a subclassed QML component hit three separate initialisation-order hazards, none of which are visible in the code. |
| **An assumption in the codebase that is simply not true** | `pyside_mvc` — the extension whose whole job is UI — implements `IExtension` nowhere, while a small `AssetValidatorExtension` sitting beside the UI code does. |
| **A number that contradicts the stated design** | The most common colour literal in the consuming app's QML was not the official accent but a near-duplicate nobody intended to create. |
| **Your own reasoning turning out wrong** | An id beginning with `_` was diagnosed as the cause of a null binding; a follow-up test disproved it. Saying so cost one line and prevented the wrong fix being trusted. |

## How to report it

Three sentences is usually enough:

1. **What was expected** — the reasonable prediction.
2. **What actually happened** — with the evidence that established it, not a
   guess.
3. **What it changes** — a decision to revisit, a risk now carried, or
   nothing at all (say that too; "surprising but harmless" is a valid and
   useful conclusion).

Do not soften it into a footnote, and do not bury it under a list of things
that went fine. If the finding invalidates something previously reported as
working, lead with it.

## Corollaries

- **A fixed surprise is still reportable.** The user needs to know the trap
  exists, not just that this instance is closed — the next one will look
  different.
- **"I was wrong" is reportable on the same terms.** An agent's discarded
  hypothesis is cheap; a user acting on a hypothesis the agent has already
  privately abandoned is not.
- **Never report a surprise as resolved without the evidence that resolved
  it.** "Fixed" following a guess is the same defect one level up.
- **Silence is a claim.** Reporting only successes asserts there were no
  surprises. If there were, that report was inaccurate regardless of how
  accurate each individual sentence in it was.
