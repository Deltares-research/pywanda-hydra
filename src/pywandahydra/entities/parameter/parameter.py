"""Module containing the parameter abstract class to be used to store in/output parameters."""

from abc import ABC, abstractmethod


class ParameterAbstract(ABC):
    """Abstract class to be used for storing parameters."""

    @abstractmethod
    def __init__(self) -> None:
        """Initializes the ParameterAbstract object."""
        pass
