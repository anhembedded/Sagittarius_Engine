from collections.abc import Callable
from typing import Any

from sagittarius_engine.interfaces import IContainer, IMiddleware

try:
    # pyrefly: ignore [missing-import]
    from pydantic import BaseModel, ValidationError
except ImportError:
    BaseModel = None
    ValidationError = None


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
        import typing

        model_class = self.model_class

        if model_class is None:
            # Dynamically infer from the handler's execute method
            try:
                type_hints = typing.get_type_hints(cmd_or_query.execute)
                for hint in type_hints.values():
                    if isinstance(hint, type) and issubclass(hint, BaseModel):
                        model_class = hint
                        break
            except Exception:
                pass

            if model_class is None:
                if isinstance(data_transfer_obj, BaseModel):
                    model_class = type(data_transfer_obj)
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
