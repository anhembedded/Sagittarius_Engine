from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sagittarius_engine.kernel.i_kernel_context import IKernelContext
import warnings

from sagittarius_engine.interfaces import IDispatcher, ILogger
from sagittarius_engine.interfaces.i_dispatchable import IDispatchable
from sagittarius_engine.interfaces.i_trace_recorder import ITraceRecorder, Lane


class Dispatcher(IDispatcher):
    """Responsible for executing handlers through the middleware pipeline."""

    def __init__(self, context: "IKernelContext") -> None:
        self.context = context

    def _get_logger(self) -> ILogger:
        return self.context.logger

    def dispatch(
        self,
        handler_class: type[IDispatchable],
        input_dto: object | None = None,
    ) -> Any:
        """
        @brief Dispatches a handler (command, query, etc.) through the middleware pipeline.

        @param handler_class Any class implementing IDispatchable (ICommand, IQuery, or custom handler).
        @param input_dto Optional DTO to pass to the handler's execute() method.
        @return The result of handler.execute(input_dto).
        """
        logger = self._get_logger()
        msg_type = "query" if "Query" in handler_class.__name__ else "command"
        logger.info(
            f"Executing {msg_type}: {handler_class.__name__}",
            extra={"submodule": "Dispatcher"},
        )
        if input_dto:
            logger.debug(f"Payload: {input_dto}", extra={"submodule": "Dispatcher"})

        handler = self.context.container.resolve(handler_class)

        # EPIC-005B. One branch, as far out as it goes: everything tracing adds
        # lives on the other side of it, so an application that never traces
        # pays a single `is None` test for the whole dispatch.
        #
        # Measured, and the reason this is shaped like this rather than as five
        # guards sprinkled through the body: scattered checks -- plus the extra
        # `try`/`finally` frames and the keyword arguments to `execute()` --
        # cost ~250 ns per dispatch with tracing off, a ~7% tax on every
        # application for a feature they had not asked for. EPIC-006F rejected
        # exactly that for its observer hook; it does not get an exception here.
        recorder = self.context.recorder

        try:
            if recorder is None:
                result = self.context.middleware_pipeline.execute(
                    handler, input_dto, lambda: handler.execute(input_dto)
                )
            else:
                result = self._dispatch_traced(
                    recorder, handler, handler_class, input_dto, msg_type
                )
            logger.debug(
                f"{handler_class.__name__} completed successfully.",
                extra={"submodule": "Dispatcher"},
            )
            return result
        except Exception as e:
            logger.error(
                f"{handler_class.__name__} failed: {e}",
                extra={"submodule": "Dispatcher"},
            )
            raise

    def _dispatch_traced(
        self,
        recorder: ITraceRecorder,
        handler: Any,
        handler_class: type[IDispatchable],
        input_dto: object | None,
        msg_type: str,
    ) -> Any:
        """
        @brief The dispatch path with tracing on: a total span, a span per
        middleware frame, and a handler span, all sharing one correlation id.

        @details Separate from `dispatch()` so the disabled path stays exactly
        as short as it was before `EPIC-005B` — see the comment there.

        The correlation id is what keeps a concurrent dispatch on another
        thread from interleaving into the same lane and reading as one
        impossible call. Both spans close in a `finally`: a dispatch that raised
        is precisely the one whose duration someone wants, and dropping it would
        leave the middleware frames inside it orphaned in the timeline.
        """
        name = handler_class.__name__
        cid = recorder.next_cid()

        def final() -> Any:
            started = recorder.span_begin(Lane.DISPATCH, name, "handler", cid)
            try:
                return handler.execute(input_dto)
            finally:
                recorder.span_end(Lane.DISPATCH, name, started, "handler", cid)

        dispatch_started = recorder.span_begin(Lane.DISPATCH, name, msg_type, cid)
        try:
            return self.context.middleware_pipeline.execute(
                handler, input_dto, final, recorder, cid
            )
        finally:
            recorder.span_end(Lane.DISPATCH, name, dispatch_started, msg_type, cid)

    def execute(self, command_class: type, input_dto: object | None = None) -> Any:
        """
        @brief Deprecated. Use dispatch instead.
        """
        warnings.warn(
            "Dispatcher.execute is deprecated. Use Dispatcher.dispatch instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.dispatch(command_class, input_dto)

    def query(self, query_class: type, input_dto: object | None = None) -> Any:
        """
        @brief Deprecated. Use dispatch instead.
        """
        warnings.warn(
            "Dispatcher.query is deprecated. Use Dispatcher.dispatch instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.dispatch(query_class, input_dto)
