---
name: Python Code Rules
description: Python coding standards, clean architecture principles, and code quality rules.
trigger: always_on
---

# PYTHON CODING STANDARDS & GUIDELINES

## SOLID Principles
Follow SOLID wherever it's practical — apply it to improve clarity/testability, don't force an abstraction onto a small, unlikely-to-change piece of code just to tick a box.
- **S — Single Responsibility:** One class/module has one reason to change. (See "No God Objects" below.)
- **O — Open/Closed:** Prefer extending behavior via a new class/strategy over editing existing, already-tested logic; put extension points behind an interface/ABC.
- **L — Liskov Substitution:** A subclass must work anywhere its base/interface is expected — no raising `NotImplementedError` on inherited methods, no narrowing accepted inputs or weakening guarantees the base type promised.
- **I — Interface Segregation:** Keep ports/interfaces narrow and role-specific; don't make an implementer satisfy methods it has no use for.
- **D — Dependency Inversion:** High-level modules depend on abstractions, not concrete implementations. (See "Full Abstraction & Decoupling" below.)

## Core Architecture Principles
1. **Strong Typing & Type Safety:**
   - Always use explicit type annotations for all function signatures, parameters, return values, and class attributes.
   - Strictly avoid using `Any`. Use `Union`, `Optional`, `Generics`, or `TypeVar` where flexiblity is needed.
   - Use `dataclasses` (with `frozen=True` where possible) or `Pydantic` models instead of raw dictionaries for complex data structures.

2. **Full Abstraction & Decoupling:**
   - Define explicit abstractions using `abc.ABC` or `typing.Protocol` for repositories, services, and external clients.
   - Adhere strictly to the Dependency Inversion Principle (DIP). High-level business logic must depend on abstractions, not concrete implementations.
   - Prefer Dependency Injection (DI) over hardcoded class instantiations inside domain logic.
   - **NO Multiple Inheritance:** Strictly avoid multiple inheritance. Use composition over inheritance, and flatten interfaces where necessary to avoid complex method resolution orders (MRO).

3. **Readability & Clean Code (Over Brevity):**
   - Follow PEP 8 guidelines. Prioritize explicit and self-documenting code over short one-liners.
   - Do NOT use complex, nested list comprehensions or multi-line `lambda` expressions when a clear `for` loop or helper function is more readable.
   - Keep functions small, focused, and single-purpose (Single Responsibility Principle). Use explicit, descriptive variable names.

4. **Immutability & Pure Functions (No Side Effects):**
   - Strive for pure functions: functions should depend only on passed arguments and produce deterministic return values.
   - Never mutate passed arguments in-place. Return new instances or modified copies instead.
   - Strictly avoid mutable default arguments (e.g., NEVER use `def func(items=[]):`).
   - Isolate side effects (I/O, DB calls, network requests) inside dedicated adapter/boundary classes.

5. **Strict Code Quality Rules:**
   - **No Magic Numbers:** Strictly avoid using raw numbers (magic numbers) in code. Define them as constants with descriptive names at the top of the file or in a dedicated configuration class.
   - **No Nested Loops:** Avoid deep nesting of loops (e.g. `for` inside `for` inside `while`). Extract nested logic into separate helper functions to reduce cyclomatic complexity and improve testability.
   - **No God Objects:** Strictly avoid creating massive classes or modules (like an overloaded `main.py` or a giant `Manager` class) that know too much or do too much. Delegate responsibilities (e.g. CLI parsing, bootstrapping, event handling) into dedicated modules.
   - **Abstract Low-Level Logic:** Do not write verbose, low-level OS/File system operations (like deep `os.path` joins or byte-level manipulation) directly in application or composition root layers. Extract them into common utility classes (e.g., `PathUtils`) inside the `sagittarius_engine.utils` directory if they are reusable across the framework.
   - **No Function-Local / Lazy Imports (Tuyệt đối không dùng Local Import):** All module, class, function, and type imports MUST be declared at the top of the file (top-level imports) adhering strictly to PEP 8. Never place `import ...` inside functions, methods, slots, test cases, or nested scopes (the only exception is `if TYPE_CHECKING:` guards at top level).
   - **Single-Scope Cohesion & Colocation (Gom chung các thành phần liên quan vào cùng 1 Scope / Single Source of Truth):** Tightly coupled components that define the same domain lifecycle, state machine, or feature configuration MUST be co-located within the same single file or module scope (e.g., FSM State Enum + FSM Event Enum + Transition Matrix + UI Mode mappings in a single `*_fsm_matrix.py`). Do NOT fragment tightly coupled definitions across multiple scattered files where understanding or modifying a single feature lifecycle requires jumping across 4-5 distant modules. Related enums, schemas, transition tables, and constants belonging to a single concept must reside together as a single source of truth.

6. **Local CI/CD Enforcement:**
   - Always run the local CI/CD script (`scripts/ci-local.ps1`) to validate your code before committing and pushing changes. It ensures linting, formatting, and tests pass.

7. **Clean Architecture Layer Enforcement:**
   - Always strictly respect the 4 Layers: Domain (Pure), Application (Use Cases/Ports), Interface Adapters (CLI/UI), and Infrastructure (DB/API/Frameworks).
   - Never leak Infrastructure concerns (like `sagittarius_engine` base classes, SQLAlchemy, or API clients) into the Domain or Application layers.

8. **Use Case Structure (CQRS):**
   - Every Application Use Case must reside in its own dedicated directory (e.g., `src/application/use_cases/my_use_case/`).
   - The Command/Response definition must be separated from the Handler logic into multiple files (e.g., `command.py` and `handler.py`), and then exported cleanly via `__init__.py`.
   - Never import engine-specific interfaces (like `sagittarius_engine.extensions.cqrs.ICommand`) into the Application layer. Use the layer's own pure Python `ICommandHandler` interface.

9. **Git Commits & Version Control:**
   - **DO NOT** commit code changes (e.g., using `git commit`) autonomously unless the user explicitly requests you to do so. Always wait for explicit permission before saving changes to version control.