from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from sagittarius_engine.interfaces.i_dispatchable import IDispatchable

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


# PEP 695 type-param syntax not applied here: ruff's own fixer declines this
# one (Generic isn't the first base), and a manual rewrite is a public-API
# syntax change better done deliberately than as a lint-cleanup rider. TASK-021.
class ICommand(Generic[TInput, TOutput], IDispatchable, ABC):  # noqa: UP046
    """
    @brief Interface for Commands in the CQRS architecture.

    @details A Command is responsible for executing operations that change the system's state
    (Write operations), such as Create, Update, or Delete.

    Generic parameters:
        TInput: The DTO type accepted by execute().
        TOutput: The result type returned by execute().
    """

    @abstractmethod
    def execute(self, input_dto: TInput) -> TOutput:  # type: ignore[override]
        """
        @brief Executes the command.
        @param input_dto The input Data Transfer Object to be processed.
        @return The execution result (if any).
        """
        ...
