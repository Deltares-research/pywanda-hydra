"""__init__.py file containing the defaults."""
from pathlib import Path

__version__ = Path(__file__).parent.joinpath("VERSION").read_text()
