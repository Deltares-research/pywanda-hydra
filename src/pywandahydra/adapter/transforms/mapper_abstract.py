"""Basic  abstract mapper class for transforming data from xlsx to pywanda-hydra object."""

from abc import ABC, abstractmethod
from typing import TypeVar


Entity = TypeVar("Entity")
XlsxObject = TypeVar("XlsxObject")


class MapperAbstract(ABC):
    """Basic mapper abstract class for transforming data from one format to another."""

    @abstractmethod
    def to_xlsx(self, entity: Entity) -> XlsxObject:
        """Maps an Entity to a xlsx object."""

    @abstractmethod
    def to_entity(self, model: XlsxObject) -> Entity:
        """Maps a xlsx object to an Entity."""
