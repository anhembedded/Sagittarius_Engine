# EPIC-001D — Runtime, Regions & Slot Registry

**Epic:** [EPIC-001 — UI Engine Foundation](../README.md)
**Status:** 🔵 Backlog
**Category:** UI Engine / Composition Runtime
**Priority:** P2 — highest value ceiling, highest design risk; deliberately sequenced last
**Depends on:** EPIC-001B, EPIC-001C

---

## 🎯 Summary & Objectives

Give the UI Engine a composition runtime: a shell that owns named regions, a registry that
screens contribute into, and a uniform screen lifecycle — so assembling a screen stops
being bespoke layout code.

### Why this is sequenced last

This layer is the most speculative of the three. It must assume which widgets exist, which
regions matter, and which surfaces are genuinely dynamic — none of which is reliably known
until EPIC-001B and EPIC-001C have landed and real screens have been built against them.
Choosing these abstractions early means choosing them with the least information, and a
wrong abstraction with live consumers is far more expensive to correct than duplicated code.

### Objectives

1. A shell owning window chrome, navigation, overlay host and named regions.
2. A registry screens contribute into, rather than a layout each screen hand-builds.
3. A uniform screen lifecycle — mount, unmount, ui_mode, shutdown — with one conformance
   test suite every screen must pass, including screens not yet written.
4. Navigation derived from screen self-description, not wired by hand.
5. **Decided 2026-08-23:** the UI Engine's own runtime lifecycle **becomes a real
   `IExtension`** of Sagittarius Engine, rather than staying deliberately outside the
   extension system. Follows the `AssetValidatorExtension` precedent (§"Two lifecycles"
   below) rather than leaving `pyside_mvc` the odd one out. See
   §"Two lifecycles" for the problem this resolves and the ordering constraint it must
   still satisfy. **[EPIC-002](../../EPIC-002_engine_sample_app_and_doc_rewrite/README.md)**
   is the first real consumer built against this decision — its sample app boots
   `pyside_mvc` through the standard `IExtension` path, not `configure_app_qml()` as a bare
   call, and reports back anything the ordering constraint (QApplication must exist first)
   makes awkward. **That prototype lives in the sample app's own code, not here** — EPIC-002B
   writes an `IExtension` wrapper as `examples/student_management` code (not
   `sagittarius_engine/`, since EPIC-002 may not touch engine source). When this subtask
   finally starts, read `examples/student_management/docs/ui_extension_lifecycle.md` and that
   wrapper first — it's a real, running answer to this objective's ordering question, not just
   a design doc. Don't re-derive the ordering from scratch if that prototype already exists.

---

## 📐 Design Constraints

Carried forward from the architecture review, to be honoured rather than rediscovered:

- **Python describes, QML renders.** A registered contribution is a *specification* —
  identity, kind, state, layout hint, action — not a visual object. Visual authority stays
  in the kit. Building visual objects in Python reintroduces imperative UI construction and
  forfeits bindings, previews and hot reload.
- **Registry state is exposed as models, not as dynamically-named context properties.** A
  per-slot model gives ordering, multiple contributions per slot, and real reactivity;
  string-concatenated context properties give one item per slot, no tooling visibility, and
  silent nulls on typos.
- **Registry is for genuinely dynamic surfaces.** Where composition is static, direct
  declaration is shorter and clearer than registration. Forcing every surface through the
  registry trades layout code for registration code without reducing either.
- **The runtime must not know the consuming application.** Contributions are fed by the
  app's own presenters/view models. A data source reaching from the domain into the UI
  runtime would collapse the separation this extension exists to provide.
- **Regions decide geometry.** A contribution expresses intent; the region resolves size
  and placement.

### Two lifecycles that currently don't talk to each other

Found 2026-08-23, verified against the reference consumer's real boot sequence, not assumed:
the UI Engine has **no connection at all** to Sagittarius Engine's own extension system.

```python
# Sagittarius_Elite_Warrior/src/presentation/ui/app_bootstrapper.py
app_engine = create_app(config_manager)
app_engine.boot()                              # real IExtension lifecycle ends here

app = QApplication(sys.argv)
...
configure_app_qml(Palette.as_ui_dict(), ...)   # UI Engine bootstrap — a bare function call,
                                                # entirely outside app_engine
```

`pyside_mvc` implements `IExtension`/`IModule` nowhere (`grep` confirms zero matches). Contrast
with `AssetValidatorExtension` — a small file living right next to the UI code in
`presentation/ui/assets/` — which *does* implement the real interface and is registered via
`app.use(AssetValidatorExtension())` alongside `LoggerExtension`, `ThreadManagerExtension`,
`HealthExtension`. The UI Engine is the odd one out, not the pattern.

**Why this likely isn't an oversight:** `configure_app_qml()` must run *after* `QApplication`
exists; `app_engine.boot()` has no notion of "wait for a GUI framework to initialize first."
Sagittarius Engine's plain `IExtension.boot(context)` doesn't obviously accommodate that
ordering constraint today — fitting the UI Engine into it isn't necessarily free.

**Concrete consequence of leaving this open:** `app_engine.shutdown()` has no path to the
`Theme` singleton, `OverlayHost`, or anything else this layer will own — a screen registry
shutting down cleanly (objective 3 above) is a *separate* lifecycle from the engine's own
shutdown, unless this question is resolved before the shell is built. Decide this — become a
real `IExtension`/`IModule`, or formalize staying outside with an explicit, documented
integration point — before finalizing objective 3's conformance suite; retrofitting after
screens depend on today's ad hoc `configure_app_qml()` call site will be the expensive path.

## 🧪 Verification & Test Coverage

- One conformance suite, applied to every registered screen: mount/unmount repeatedly
  without leaking; shutdown cleanly while background work is in flight; respond correctly
  to every ui_mode; declare complete metadata.
- Contributions render into the correct region, in declared order, and survive
  add/remove/reorder.
- Navigation reflects registered screens with no hand-written wiring.
- A screen that violates the contract fails the suite rather than failing at runtime.
