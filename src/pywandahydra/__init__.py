"""pywandahydra — Scenario runner for the pywanda package."""

from pathlib import Path

__version__ = Path(__file__).parent.joinpath("VERSION").read_text().strip()


def main() -> None:
    """CLI entry point."""
    from pywandahydra.cli.commands import app

    app()
