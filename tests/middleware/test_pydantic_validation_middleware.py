from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from sagittarius_engine.middleware.pydantic_validation_middleware import (
    PydanticValidationMiddleware,
)

if TYPE_CHECKING:
    # Imported only for the type checker, exactly like the TYPE_CHECKING idiom
    # TASK-026 is about (IModule.register, ITaskManager.spawn, ...): mypy resolves
    # this name statically, but it is never bound in this module's runtime globals,
    # so typing.get_type_hints() raises NameError against it at runtime.
    from sagittarius_engine.interfaces import IContainer as UnresolvableAtRuntimeType


class MyDTO(BaseModel):
    name: str
    age: int


class DummyObj:
    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age


class DummyCommand:
    pass


class AutoInferCommand:
    """@brief A handler with a resolvable Pydantic type hint and no explicit model_class."""

    def execute(self, dto: MyDTO) -> None: ...


class UnresolvableCommand:
    """@brief A handler whose execute() annotation cannot resolve at runtime — the
    TYPE_CHECKING / missing-import shape TASK-026 is about."""

    def execute(self, dto: "UnresolvableAtRuntimeType") -> None: ...


def test_init_raises_import_error_when_pydantic_missing():
    with (
        patch(
            "sagittarius_engine.middleware.pydantic_validation_middleware.BaseModel",
            None,
        ),
        pytest.raises(ImportError, match="pydantic is not installed"),
    ):
        PydanticValidationMiddleware(container=None)


def test_successful_validation_with_dict():
    middleware = PydanticValidationMiddleware(container=None)
    middleware.model_class = MyDTO
    called = False

    def next_handler():
        nonlocal called
        called = True
        return "success"

    data = {"name": "Alice", "age": 30}
    result = middleware.process(DummyCommand(), data, next_handler)

    assert called
    assert result == "success"


def test_successful_validation_with_none():
    class OptionalDTO(BaseModel):
        name: str = "default"
        age: int = 0

    middleware = PydanticValidationMiddleware(container=None)
    middleware.model_class = OptionalDTO
    called = False

    def next_handler():
        nonlocal called
        called = True
        return "success"

    result = middleware.process(DummyCommand(), None, next_handler)

    assert called
    assert result == "success"


def test_successful_validation_with_model_instance():
    middleware = PydanticValidationMiddleware(container=None)
    middleware.model_class = MyDTO
    called = False

    def next_handler():
        nonlocal called
        called = True
        return "success"

    data = MyDTO(name="Bob", age=25)
    result = middleware.process(DummyCommand(), data, next_handler)

    assert called
    assert result == "success"


def test_successful_validation_with_object_dict():
    middleware = PydanticValidationMiddleware(container=None)
    middleware.model_class = MyDTO
    called = False

    def next_handler():
        nonlocal called
        called = True
        return "success"

    data = DummyObj("Charlie", 40)
    result = middleware.process(DummyCommand(), data, next_handler)

    assert called
    assert result == "success"


def test_validation_failure_raises_value_error():
    middleware = PydanticValidationMiddleware(container=None)
    middleware.model_class = MyDTO

    def next_handler():
        pass

    data = {"name": "Dave"}  # Missing age

    with pytest.raises(ValueError, match="Validation failed for DummyCommand"):
        middleware.process(DummyCommand(), data, next_handler)


def test_v1_fallback_dict():
    # Create a mock V1 model class
    class V1DTO:
        def __init__(self, **kwargs):
            self.name = kwargs.get("name")
            self.age = kwargs.get("age")
            if not self.name or not self.age:
                pass

        def __eq__(self, other):
            return self.name == other.name and self.age == other.age

    middleware = PydanticValidationMiddleware(container=None)
    middleware.model_class = V1DTO
    called = False

    def next_handler():
        nonlocal called
        called = True
        return "success"

    data = {"name": "Eve", "age": 22}
    result = middleware.process(DummyCommand(), data, next_handler)

    assert called
    assert result == "success"


def test_v1_fallback_none():
    class V1DTO:
        def __init__(self):
            self.name = "default"
            self.age = 0

    middleware = PydanticValidationMiddleware(container=None)
    middleware.model_class = V1DTO
    called = False

    def next_handler():
        nonlocal called
        called = True
        return "success"

    result = middleware.process(DummyCommand(), None, next_handler)

    assert called
    assert result == "success"


def test_v1_fallback_object_dict():
    class V1DTO:
        def __init__(self, **kwargs):
            self.name = kwargs.get("name")
            self.age = kwargs.get("age")

    middleware = PydanticValidationMiddleware(container=None)
    middleware.model_class = V1DTO
    called = False

    def next_handler():
        nonlocal called
        called = True
        return "success"

    data = DummyObj("Frank", 50)
    result = middleware.process(DummyCommand(), data, next_handler)

    assert called
    assert result == "success"


def test_auto_infers_model_class_from_resolvable_type_hints():
    """@brief TASK-026 requirement 4: a handler whose hints resolve gets validated."""
    middleware = PydanticValidationMiddleware(container=None)

    def next_handler():
        return "success"

    valid = middleware.process(
        AutoInferCommand(), {"name": "Hank", "age": 44}, next_handler
    )
    assert valid == "success"

    # Proves inference actually wired up validation (not a silent pass-through):
    # invalid data must still be rejected.
    with pytest.raises(ValueError, match="Validation failed for AutoInferCommand"):
        middleware.process(AutoInferCommand(), {"name": "Hank"}, next_handler)


def test_unresolvable_type_hints_logs_and_dispatches_unvalidated(caplog):
    """@brief TASK-026 requirement 1/2/4: get_type_hints() failing must not be
    silent, and the chosen policy (fail open, loudly) still dispatches the request."""
    middleware = PydanticValidationMiddleware(container=None)
    called = False

    def next_handler():
        nonlocal called
        called = True
        return "success"

    with caplog.at_level(
        "WARNING", logger="sagittarius_engine.middleware.pydantic_validation_middleware"
    ):
        result = middleware.process(
            UnresolvableCommand(), {"name": "Ivy", "age": 1}, next_handler
        )

    assert called
    assert result == "success"
    assert any("get_type_hints" in record.message for record in caplog.records)
    assert any(
        record.levelname == "ERROR"
        and "dispatching UnresolvableCommand unvalidated" in record.message
        for record in caplog.records
    )


def test_unresolvable_type_hints_still_validates_a_model_instance(caplog):
    """@brief Even when hints can't resolve, a DTO that already IS a BaseModel
    instance must still be validated against its own type — only the "we truly
    cannot tell" case falls back to unvalidated dispatch."""
    middleware = PydanticValidationMiddleware(container=None)

    def next_handler():
        return "success"

    with caplog.at_level(
        "WARNING", logger="sagittarius_engine.middleware.pydantic_validation_middleware"
    ):
        result = middleware.process(
            UnresolvableCommand(), MyDTO(name="Jack", age=2), next_handler
        )

    assert result == "success"
    assert any("get_type_hints" in record.message for record in caplog.records)
    assert not any(record.levelname == "ERROR" for record in caplog.records)


def test_v1_fallback_model_instance():
    class V1DTO:
        def __init__(self, **kwargs):
            self.name = kwargs.get("name")
            self.age = kwargs.get("age")

    middleware = PydanticValidationMiddleware(container=None)
    middleware.model_class = V1DTO
    called = False

    def next_handler():
        nonlocal called
        called = True
        return "success"

    data = V1DTO(name="Grace", age=33)
    result = middleware.process(DummyCommand(), data, next_handler)

    assert called
    assert result == "success"
