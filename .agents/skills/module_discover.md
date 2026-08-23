---
name: module_discover
description: Investigates a specified module in the codebase and generates comprehensive documentation detailing its architecture, API, usage, and common misconceptions.
---

# Skill: Discover and Document Module

When the user requests you to "discover", "investigate", or "document" a specific module, subsystem, or feature in the codebase (e.g., `Config`, `EventBus`, `TaskManager`), follow these rigorous steps to ensure a comprehensive understanding and high-quality documentation output.

## Execution Steps

### 1. Research the Core Abstractions (Interfaces)

- Use the repo's actual search/read tools to find the core interfaces related to the module.
- Look for these interfaces in the relevant project directories rather than assuming a single fixed folder.
- Read the source code of the interface to understand its public API contracts, type hints, and intended responsibilities.

### 2. Identify Implementations and Concrete Classes

- Use `grep_search` to find classes that implement the core interfaces (e.g., search for `class [A-Za-z0-9_]+\(IConfig\):`).
- Check the `sagittarius_engine/infrastructure/`, `sagittarius_engine/kernel/`, or `sagittarius_engine/runtime/` directories for concrete implementations.
- Understand how each implementation differs (e.g., `DictConfig` vs `ConfigManager`, or `MemoryEventBus` vs `AsyncioEventBus`).

### 3. Trace Integration and Usage

- Investigate how the module is registered into the Dependency Injection container (usually in a module's `register(app)` method or Bootstrap phase).
- Check the `examples/` directory (e.g., `student_management`) and `tests/` to see how the module is practically used by application developers.
- Trace any background threads, `EventBus` signals, or hooks to `TaskManager` the module might be using.

### 4. Synthesize and Write Documentation

Once you have fully understood the module, create a highly detailed Markdown document in
`.agents/context/modules/[ModuleName].md` (create the `modules/` subdirectory if it doesn't
exist yet — the top-level `docs/Modules/` this skill used to point at was deleted from the repo
in commit `a338d42` and never rebuilt; see `.agents/context/repository.md`'s `docs/` row).
The document **must** follow this strict structure:

#### Document Structure Template

1. **Overview**: What the module is, its responsibility in the Clean Architecture, and why it exists.
2. **Terminology**: Define any domain-specific terms, acronyms, or concepts unique to this module to ensure readers share a common vocabulary before diving deeper.
3. **Use Cases**: Detail specific real-world scenarios or workflows where this module should be used (e.g., When and why to use this module to solve a specific problem).
4. **How it works**: Deep dive into the internal mechanics, dependency injection bindings, caching behaviors, thread safety, or runtime lifecycles.
5. **Components & API**:
   - Detail the primary Interface(s) and their methods.
   - Detail the concrete Implementations and when to use which (e.g., use X for Production, Y for Testing).
6. **Code Examples & Usage Guide**:
   - Provide concrete, copy-pasteable Python code blocks showing how to initialize, configure, and use the module for the specific Use Cases identified above.
   - Show both simple usage and advanced usage.
7. **Common Misconceptions (Module & Use Cases)**:
   - List at least 3-4 misconceptions or "gotchas" developers might have about this module or **its use cases** (e.g., using it for the wrong problem, performance assumptions, blocking behaviors) and explicitly state the **Truth**.

### 5. Finalize

- Provide a summary to the user outlining the key discoveries you made.
- Point them to the newly generated documentation file in `.agents/context/modules/`.
