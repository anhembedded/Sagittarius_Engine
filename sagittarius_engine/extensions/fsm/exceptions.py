class FSMError(Exception):
    """
    @brief Base exception class for all FSM-related errors.
    """


class InvalidStateTransitionError(FSMError):
    """
    @brief Raised when an invalid state transition or event dispatch is attempted.
    """

    def __init__(
        self,
        from_state: str,
        to_state: str = "UNKNOWN",
        event: str | None = None,
    ):
        if event is not None:
            msg = f"Invalid transition from state '{from_state}' via event '{event}'."
        else:
            msg = f"Invalid transition from '{from_state}' to '{to_state}'."
        super().__init__(msg)
        self.from_state = from_state
        self.to_state = to_state
        self.event = event
