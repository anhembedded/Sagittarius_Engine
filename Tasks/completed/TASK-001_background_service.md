# TASK-001: Implement `BackgroundService` Pattern for Hosted Services

- **Status**: ✅ Completed
- **Category**: Architecture / Hosted Services
- **Completed Date**: 2026-07-28

---

## 🎯 Summary & Objectives
Introduced the `BackgroundService(IHostedService)` abstract base class in `sagittarius_engine.runtime` to simplify long-running background tasks (like CLI menus, polling workers, and queue consumers).

---

## 📐 Implementation Overview

### 1. `BackgroundService` Implementation
File: [background_service.py](../../sagittarius_engine/runtime/hosted/background_service.py)

```python
from abc import abstractmethod
from typing import Optional
from sagittarius_engine.interfaces import IEngineContext, ITaskHandle
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


class BackgroundService(IHostedService):
    def __init__(self) -> None:
        self.token = CancellationToken()
        self.task: Optional[ITaskHandle] = None

    def start(self, context: IEngineContext) -> None:
        self.task = context.tasks.spawn(
            self._run_wrapper, name=self.__class__.__name__, token=self.token
        )

    def _run_wrapper(self, token: CancellationToken) -> None:
        self.run(token)

    @abstractmethod
    def run(self, token: CancellationToken) -> None:
        pass

    def stop(self, context: IEngineContext) -> None:
        self.token.cancel()
```

---

## 🧪 Verification & Test Coverage
- **Unit Test**: `test_background_service_pattern()` in [test_runtime.py](../../tests/runtime/test_runtime.py) (Passed)
- **Static Analysis**: `mypy` and `ruff check` (0 errors)
