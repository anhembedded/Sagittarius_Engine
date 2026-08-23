from typing import Any

from sagittarius_engine.extensions.persistence.i_session import ISession


class SQLAlchemySessionAdapter(ISession):
    """
    @brief Adapter for SQLAlchemy Session.
    """

    def __init__(self, session: Any):
        self.session = session

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def execute(self, statement: Any, params: Any = None) -> Any:
        return self.session.execute(statement, params)

    def query(self, *entities: Any) -> Any:
        return self.session.query(*entities)

    def add(self, entity: Any) -> None:
        self.session.add(entity)

    def get(self, entity_class: type, entity_id: Any) -> Any | None:
        return self.session.get(entity_class, entity_id)

    def merge(self, entity: Any) -> Any:
        return self.session.merge(entity)

    def delete(self, entity: Any) -> None:
        self.session.delete(entity)

    def close(self) -> None:
        if hasattr(self.session, "remove"):
            self.session.remove()
        elif hasattr(self.session, "close"):
            self.session.close()
