import inspect
import logging
import typing
from collections.abc import Callable
from typing import Any

from sagittarius_engine.interfaces import IContainer, IMiddleware

try:
    # pyrefly: ignore [missing-import]
    from pydantic import BaseModel, ValidationError
except ImportError:
    BaseModel = None
    ValidationError = None

logger = logging.getLogger(__name__)


class PydanticValidationMiddleware(IMiddleware):
    """
    @brief Middleware used to validate input DTOs using Pydantic models.

    @details Validates the provided DTO against the given Pydantic model class.
    If the DTO is a dictionary, it will be unpacked. If validation fails,
    an exception is raised or logged.

    @par Requirement:
    Requires the `pydantic` package to be installed.

    @par Tutorial / Usage Example:
    @code
    from pydantic import BaseModel

    class MyDTO(BaseModel):
        name: str
        age: int

    app.use_middleware(PydanticValidationMiddleware(MyDTO))
    @endcode
    """

    def __init__(
        self, container: IContainer | None = None, model_class: Any = None
    ) -> None:
        """
        @brief Constructor.
        @param model_class The Pydantic BaseModel class used for validation.
        """
        if BaseModel is None:
            raise ImportError(
                "pydantic is not installed. Please install it using `pip install pydantic`."
            )
        self.container = container
        self.model_class = model_class

    def _infer_model_class(self, cmd_or_query: Any) -> tuple[type[Any] | None, bool]:
        """
        @brief Infers a Pydantic model class from the handler's execute() type hints.

        @details Tries typing.get_type_hints() first. If that raises — e.g. a
        TYPE_CHECKING-only import, or a genuinely missing import elsewhere on the
        signature (invisible under Python 3.14's deferred annotations until something
        forces resolution) — falls back to the raw, unresolved annotations from
        inspect.signature() so one unrelated forward reference does not by itself
        defeat inference, mirroring StdLibContainer's dependency-resolution fallback.

        @param cmd_or_query The Command or Query instance being executed.
        @return A tuple of (the first BaseModel subclass found, or None; whether
        get_type_hints() raised, so the caller can tell a genuine resolution failure
        apart from a handler that simply has no Pydantic DTO in its signature).
        """
        execute = cmd_or_query.execute
        handler_name = cmd_or_query.__class__.__name__

        try:
            hints: dict[str, Any] = typing.get_type_hints(execute)
            had_resolution_error = False
        except Exception as exc:
            logger.warning(
                "PydanticValidationMiddleware: typing.get_type_hints() failed for "
                "%s.execute (%s: %s); falling back to raw, unresolved annotations",
                handler_name,
                type(exc).__name__,
                exc,
            )
            hints = {
                name: param.annotation
                for name, param in inspect.signature(execute).parameters.items()
                if param.annotation is not inspect.Parameter.empty
            }
            had_resolution_error = True

        for hint in hints.values():
            if isinstance(hint, type) and issubclass(hint, BaseModel):
                logger.debug(
                    "PydanticValidationMiddleware: inferred model %s for %s",
                    hint.__name__,
                    handler_name,
                )
                return hint, had_resolution_error

        return None, had_resolution_error

    def process(
        self, cmd_or_query: Any, data_transfer_obj: Any, next_handler: Callable[[], Any]
    ) -> Any:
        """
        @brief Validates the DTO using the provided Pydantic model.

        @param cmd_or_query The Command or Query instance being executed.
        @param data_transfer_obj The Data Transfer Object input to validate.
        @param next_handler The next middleware or the final execution function.
        @return The result of the operation.
        @exception ValueError if validation fails.
        """
        model_class = self.model_class

        if model_class is None:
            model_class, had_resolution_error = self._infer_model_class(cmd_or_query)

            if model_class is None:
                if isinstance(data_transfer_obj, BaseModel):
                    model_class = type(data_transfer_obj)
                elif had_resolution_error:
                    # Policy: fail open, loudly (see TASK-026). This middleware is
                    # typically installed globally across every command/query, not
                    # scoped to Pydantic-validated ones, so raising here would break
                    # any handler whose execute() has an unrelated unresolvable
                    # annotation even when it never intended Pydantic validation at
                    # all. The WARNING above names the real cause; this ERROR marks
                    # the moment validation was actually skipped as its consequence,
                    # so the two can be traced together instead of vanishing silently.
                    logger.error(
                        "PydanticValidationMiddleware: dispatching %s unvalidated — "
                        "model_class could not be determined because its execute() "
                        "type hints failed to resolve. Pass model_class explicitly "
                        "to this middleware to bypass inference.",
                        cmd_or_query.__class__.__name__,
                    )
                    return next_handler()
                else:
                    return next_handler()

        try:
            if hasattr(model_class, "model_validate"):
                # Pydantic V2
                if data_transfer_obj is None:
                    validated_dto = model_class()
                elif isinstance(data_transfer_obj, dict):
                    validated_dto = model_class.model_validate(data_transfer_obj)
                elif isinstance(data_transfer_obj, model_class):
                    validated_dto = data_transfer_obj
                else:
                    try:
                        validated_dto = model_class.model_validate(data_transfer_obj)
                    except Exception:
                        dto_dict = (
                            data_transfer_obj.__dict__
                            if hasattr(data_transfer_obj, "__dict__")
                            else {}
                        )
                        validated_dto = model_class.model_validate(dto_dict)
            else:
                # Pydantic V1 fallback
                if data_transfer_obj is None:
                    validated_dto = model_class()
                elif isinstance(data_transfer_obj, dict):
                    validated_dto = model_class(**data_transfer_obj)
                elif isinstance(data_transfer_obj, model_class):
                    validated_dto = data_transfer_obj
                else:
                    dto_dict = (
                        data_transfer_obj.__dict__
                        if hasattr(data_transfer_obj, "__dict__")
                        else {}
                    )
                    validated_dto = model_class(**dto_dict)
            data_transfer_obj = validated_dto
        except ValidationError as e:
            raise ValueError(
                f"Validation failed for {cmd_or_query.__class__.__name__}: {e}"
            )

        return next_handler()
