import functools
from collections.abc import Callable
from typing import Any, TypeVar

from sagittarius_engine.interfaces import IMiddleware
from sagittarius_engine.interfaces.i_trace_recorder import ITraceRecorder, Lane

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
        recorder: ITraceRecorder | None = None,
        cid: int = 0,
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
        if recorder is None:
            # Hoisted out of the loop, and this whole branch is byte-for-byte
            # what the pipeline did before EPIC-005B. Checking per middleware
            # instead cost applications that never trace ~250 ns per dispatch --
            # the same ~7% tax EPIC-006F rejected for its observer hook, and
            # rejected again here rather than granted an exception.
            for middleware in reversed(self.middlewares):
                next_handler = functools.partial(
                    middleware.process, cmd_or_query, dto, next_handler
                )
            return next_handler()

        for middleware in reversed(self.middlewares):
            # EPIC-005B. A span per frame is the only way to see which
            # middleware in a chain is the expensive one — `EPIC-005` calls
            # this out as "currently unanswerable by any means", and it is:
            # the frames are nested `functools.partial` calls that a sampling
            # profiler renders as one indistinguishable stack.
            next_handler = _traced_frame(
                middleware, cmd_or_query, dto, next_handler, recorder, cid
            )
        return next_handler()


def _traced_frame(
    middleware: IMiddleware,
    cmd_or_query: object,
    dto: object | None,
    next_handler: Callable[[], Any],
    recorder: ITraceRecorder,
    cid: int,
) -> Callable[[], Any]:
    """
    @brief One middleware frame, wrapped in a span.

    @details A module-level function rather than a closure inside the loop:
    Python's late binding would make every frame report the *last* middleware's
    name, which is the classic loop-variable-capture bug and would produce a
    trace that is confidently wrong rather than merely absent.
    """
    name = type(middleware).__name__

    def frame() -> Any:
        started = recorder.span_begin(Lane.MIDDLEWARE, name, cid=cid)
        try:
            return middleware.process(cmd_or_query, dto, next_handler)
        finally:
            recorder.span_end(Lane.MIDDLEWARE, name, started, cid=cid)

    return frame
