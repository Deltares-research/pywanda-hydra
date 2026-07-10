"""Example script demonstrating how to run a surge-vessel optimization from a config.

Reproduces the optimization routine of *van der Zwan et al. 2012 — "Optimization of
surge protection for a large water transmission scheme in Abu Dhabi"* for a WANDA
model containing an inclined surge vessel.

For production use, prefer the CLI::

    pywandahydra optimize examples/data/optimization_config.json --workers 4
"""

from __future__ import annotations

import argparse
import faulthandler
import logging
import os
import sys
from importlib.util import find_spec
from pathlib import Path

from pywandahydra.app_logging import setup_logging
from pywandahydra.optimization.config import (
    load_optimization_config,
    validate_optimization_paths,
)
from pywandahydra.optimization.runner import run_optimization

# Enable console logging to see all pywandahydra messages, in developer mode.
setup_logging(logging.DEBUG)

# Suppress verbose third-party debug logs while keeping pywandahydra debug logs.
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)


def _print_startup_banner() -> None:
    """Print runtime details to make environment mismatches obvious."""
    pywandahydra_spec = find_spec("pywandahydra")
    pywanda_spec = find_spec("pywanda")

    print("=== PyWandaHydra Startup Banner ===")
    print(f"python.executable: {sys.executable}")
    print(f"cwd: {os.getcwd()}")
    print(f"sys.path[0]: {sys.path[0] if sys.path else ''}")
    print(
        f"pywandahydra.location: {pywandahydra_spec.origin if pywandahydra_spec else 'NOT FOUND'}"
    )
    print(f"pywanda.location: {pywanda_spec.origin if pywanda_spec else 'NOT FOUND'}")
    print("===================================")


def main() -> None:
    """Run a surge-vessel optimization using settings from a JSON config file."""
    # Dump the Python stack to stderr on a native crash (an access violation in
    # the pywanda/WANDA DLLs kills the process without a traceback otherwise).
    faulthandler.enable()

    _print_startup_banner()

    repo_root = Path(__file__).parent
    default_config = repo_root / "data" / "optimization_config_hexatech.json"

    parser = argparse.ArgumentParser(
        description="Run a PyWandaHydra surge-vessel optimization from a JSON config file."
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=default_config,
        type=Path,
        help=f"Path to optimization config JSON (default: {default_config})",
    )
    parser.add_argument(
        "--c-unit",
        default="",
        help="Unit label for the C-value axis in the output plot (e.g. 'J').",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip rendering the acceptable-range plot.",
    )
    args = parser.parse_args()

    config_path = args.config.expanduser().resolve()
    cfg = load_optimization_config(config_path)
    validate_optimization_paths(cfg, config_dir=config_path.parent)

    try:
        results = run_optimization(
            cfg,
            c_unit=args.c_unit,
            render_plot=not args.no_plot,
        )

        if results.min_feasible_vessels is None:
            print(
                "\nOptimization complete: no feasible surge-vessel count found "
                "within the given bounds."
            )
        else:
            print(
                "\nOptimization complete: minimum feasible number of surge vessels = "
                f"{results.min_feasible_vessels}"
            )

        run_root = cfg.output_root / cfg.run_id
        print(f"Results written to: {run_root}")
        print(f"  - {run_root / 'optimization_results.json'}")
        print(f"  - {run_root / 'optimization_results.csv'}")
        if not args.no_plot:
            print(f"  - {run_root / 'figures' / 'acceptable_c_range.png'}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
