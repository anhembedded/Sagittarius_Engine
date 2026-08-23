import functools
from collections.abc import Callable
from typing import TypeVar

from sagittarius_engine.interfaces import IMiddleware

TOutput = TypeVar("TOutput")


class MiddlewarePipeline:
    """
    Manages a chain of Middlewares using the Onion execution pattern:
    - Requests flow inward through each middleware until they reach the core handler.
    - Results flow outward back through the middleware chain.
    """

    def __init__(self) -> None:
        self.middlewares: list[IMiddleware] = []

    def add(self, middleware: IMiddleware) -> None:
        """Append a middleware to the end of the chain."""
        self.middlewares.append(middleware)

    def execute(
        self,
        cmd_or_query: object,
        dto: object | None,
        final_handler: Callable[[], TOutput],
    ) -> TOutput:
        """
        Execute the entire middleware chain.

        Args:
            cmd_or_query: The Command or Query instance.
            dto: The Data Transfer Object input.
            final_handler: The final execution handler for the Command/Query.

        Returns:
            The final execution result after passing through the pipeline.
        """
        # Optimization: Use functools.partial in a flat iteration instead of
        # recursive lambdas to build the execution chain. This avoids dynamic
        # lambda closure creation overhead during execution and reduces call stack depth.
        next_handler = final_handler
        for middleware in reversed(self.middlewares):
            next_handler = functools.partial(
                middleware.process, cmd_or_query, dto, next_handler
            )
        return next_handler()
