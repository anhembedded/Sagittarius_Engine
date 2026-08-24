# BUG-007 — `ResilientEventBus.on()` silently drops a subscription when two event classes share a `__name__`

**Reported date:** 2026-08-25
**Severity:** Medium (a subscription that never fires, with no error and no log — the failure is total and invisible)
**Status:** 🔴 Open
**Found by:** `EPIC-008C`, reading the event buses while fixing handler-failure reporting

---

## What is wrong

`ResilientEventBus` keys its internal `_wrapper_map` by the event's **`__name__`**:

```python
event_name = (
    event_name_or_type
    if isinstance(event_name_or_type, str)
    else getattr(event_name_or_type, "__name__", str(event_name_or_type))
)
```

while every other bus — and `MemoryEventBus._get_event_key`, which is what actually resolves
the key on the inner bus — uses `event_name` if present and otherwise **`__qualname__`**.

`on()` then early-returns when the key is already present:

```python
key = (event_name, handler)
if key in self._wrapper_map:
    return
```

So two distinct event classes that share a bare `__name__` but differ in `__qualname__`
collide, and the second `on()` call returns without registering anything — no exception, no
log, nothing.

## Reproduction

```python
def make_a():
    class Evt: pass
    return Evt

def make_b():
    class Evt: pass
    return Evt

A, B = make_a(), make_b()
# A.__name__ == B.__name__ == "Evt"
# A.__qualname__ == "make_a.<locals>.Evt", B.__qualname__ == "make_b.<locals>.Evt"

bus = ResilientEventBus(inner_bus=MemoryEventBus(), max_retries=0)
seen = []
bus.on(A, lambda d: seen.append("called"))
bus.on(B, lambda d: seen.append("called"))   # silently does nothing

bus.emit(B())
```

Actual output:

```text
wrapper_map keys: ['Evt']
handler ran for B? []
```

The handler subscribed to `B` never runs.

## Why it is worth fixing rather than ignoring

Nested and locally-defined event classes are not exotic — every dataclass event defined inside
a test function or a factory has a `__qualname__`-only distinction, and `EPIC-008B`'s
`EventRegistry` deliberately keys on `event_name`/`__qualname__` precisely because
`__name__` is not unique. This bus is the one place in the package still keying on `__name__`,
which makes it the one place where the registry and the bus can disagree about what event a
subscription is for.

It is also silent, which is the property that makes it expensive: a subscriber that never fires
looks identical to a subscriber whose event never happened.

## Requirements

1. Resolve the key the same way the rest of the package does. `MemoryEventBus._get_event_key`
   is the existing implementation of that rule — the fix should **reuse** it rather than add a
   fourth hand-rolled copy (`ResilientEventBus`, `ThreadPoolEventBus` and `IpcQueueEventBus`
   each inline their own variant today; consolidating them is the durable fix and matches how
   `EPIC-008C` handled the duplicated failure-reporting logic).
2. Decide what `on()` should do when the same `(event, handler)` really is registered twice.
   The current early-return makes double-subscription a no-op; that is defensible, but it must
   be deliberate and tested, not a side effect of a colliding key.
3. Regression test using two classes with the same `__name__` and different `__qualname__`,
   asserting both handlers fire. It must fail on today's code — paste both runs.
4. `pwsh ./scripts/ci-local.ps1` green — paste the `===CI_LOCAL_RESULT===` block and the log path.

## Deliberately not fixed inside `EPIC-008C`

`EPIC-008C`'s scope is handler-failure visibility and log levels. This is a distinct defect in
subscription bookkeeping with its own risk (changing key resolution changes which handlers an
existing consumer's `off()` calls can find), so it gets its own change rather than riding along
— `design-discipline.md`: "prefer leaving something undone and named over done and wrong".
