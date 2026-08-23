from typing import Any, TypeVar

from sagittarius_engine.extensions.persistence.i_session import ISession

T = TypeVar("T")
TId = TypeVar("TId", bound=Any)


class BaseRepository[T, TId: Any]:
    """
    @brief Base generic Repository for entity CRUD operations.

    @details Provides standard add, get_by_id, list_all, update, and delete methods.
    Requires an ISession instance to perform database operations.
    """

    def __init__(self, session: ISession, entity_class: type[T]) -> None:
        """
        @brief Constructor.
        @param session The database session.
        @param entity_class The class of the entity this repository manages.
        """
        self.session = session
        self.entity_class = entity_class

    def add(self, entity: T) -> None:
        """
        @brief Adds a new entity to the database.
        @param entity The entity to add.
        """
        self.session.add(entity)

    def get_by_id(self, entity_id: TId) -> T | None:
        """
        @brief Retrieves an entity by its ID.
        @param entity_id The ID of the entity.
        @return The entity if found, otherwise None.
        """
        return self.session.get(self.entity_class, entity_id)

    def list_all(self) -> list[T]:
        """
        @brief Lists all entities of this type.
        @return A list of entities.
        """
        return self.session.query(self.entity_class).all()

    def update(self, entity: T) -> None:
        """
        @brief Updates an existing entity.
        @param entity The entity to update.
        """
        self.session.merge(entity)

    def delete(self, entity: T) -> None:
        """
        @brief Deletes an entity.
        @param entity The entity to delete.
        """
        self.session.delete(entity)
