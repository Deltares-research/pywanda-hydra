"""pywandahydra - Scenario runner for the pywanda package."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Silent by default for library consumers; call app_logging.setup_logging()
# (or the CLI's --log-level option) to enable output.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__version__ = Path(__file__).parent.joinpath("VERSION").read_text().strip()

if TYPE_CHECKING:
    from .run import ValidationReport

__all__ = [
    "ValidationReport",
    "execute_run",
    "postprocess_run",
    "prepare_run",
    "read_run_status",
    "validate_run",
]


def __getattr__(name: str) -> Any:
    """Load supported application APIs only when callers request them."""
    if name in __all__:
        from . import run

        return getattr(run, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> None:
    """CLI entry point."""
    from pywandahydra.cli import app

    app()
