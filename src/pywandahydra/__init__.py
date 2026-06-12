"""pywandahydra — Scenario runner for the pywanda package."""

from pathlib import Path

from pywandahydra._dll_preload import preload_msvc_runtime

# Must happen before pandas/pyarrow load their bundled (stale) MSVC runtime,
# which otherwise crashes pywanda.WandaModel with an access violation.
preload_msvc_runtime()

__version__ = Path(__file__).parent.joinpath("VERSION").read_text().strip()


def main() -> None:
    """CLI entry point."""
    from pywandahydra.cli.commands import app

    app()
