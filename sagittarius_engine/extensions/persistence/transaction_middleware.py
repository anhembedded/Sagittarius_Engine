from collections.abc import Callable
from typing import Any

from sagittarius_engine.extensions.persistence import ISession
from sagittarius_engine.interfaces import IContainer, IMiddleware


class TransactionMiddleware(IMiddleware):
    """
    @brief Middleware for managing database transactions.

    @details This middleware dynamically resolves an `ISession` from the container,
    wraps the command execution in a transaction, and commits the transaction if the
    command succeeds, or rolls back if an exception occurs.
    """

    def __init__(self, container: IContainer):
        self._container = container

    def process(
        self, cmd_or_query: Any, data_transfer_obj: Any, next_handler: Callable[[], Any]
    ) -> Any:
        session: ISession = self._container.resolve(ISession)
        try:
            result = next_handler()
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
