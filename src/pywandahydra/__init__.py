"""pywandahydra — Scenario runner for the pywanda package."""

import logging
from pathlib import Path

# Silent by default for library consumers; call app_logging.setup_logging()
# (or the CLI's --log-level option) to enable output.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__version__ = Path(__file__).parent.joinpath("VERSION").read_text().strip()


def main() -> None:
    """CLI entry point."""
    from pywandahydra.cli.commands import app

    app()
