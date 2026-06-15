"""Example script demonstrating how to run PyWandaHydra from a YAML config.

For production use, prefer the CLI::

    pywandahydra run test_data/run_config.yaml --workers 4 --resume
"""

from __future__ import annotations

import argparse
import faulthandler
import json
import logging
import os
import sys
from importlib.util import find_spec
from pathlib import Path

from pywandahydra.app_logging import setup_logging
from pywandahydra.config.loader import (
    RunMetadata,
    apply_post_processing_overrides,
    build_run_context,
    load_run_config,
    validate_run_paths,
)
from pywandahydra.execution.artifacts import create_run_directories
from pywandahydra.execution.runner import run
from pywandahydra.scenarios.mapper import load_scenarios
from pywandahydra.wanda.validation import assert_preflight_valid

# Enable console logging to see all pywandahydra messages, in developer mode.
setup_logging(logging.DEBUG)

# Suppress verbose third-party debug logs while keeping pywandahydra debug logs
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
    """Run scenarios using settings loaded from a YAML config file."""
    # Dump the Python stack to stderr on a native crash (access violation intea
    # pywanda/WANDA DLLs kills the process without a traceback otherwise).
    faulthandler.enable()

    _print_startup_banner()

    repo_root = Path(__file__).parents[1]
    default_config = repo_root / "test_data" / "run_config.yaml"

    parser = argparse.ArgumentParser(
        description="Run PyWandaHydra scenarios from a YAML config file."
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=default_config,
        type=Path,
        help=f"Path to run config YAML (default: {default_config})",
    )
    args = parser.parse_args()

    config_path = args.config.expanduser().resolve()
    cfg = load_run_config(config_path)
    validate_run_paths(cfg, config_dir=config_path.parent)

    scenario_path = cfg.scenario_file
    if not scenario_path.is_absolute():
        scenario_path = config_path.parent / scenario_path

    scenarios = load_scenarios(path=scenario_path)
    assert_preflight_valid(model_spec=cfg.model, scenarios=scenarios)
    apply_post_processing_overrides(cfg, scenarios)
    ctx = build_run_context(cfg)

    run_root = Path(ctx.root_dir)
    create_run_directories(ctx, config_path=config_path)
    run_metadata = RunMetadata()
    metadata_path = run_root / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(run_metadata.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )

    try:
        result = run(
            model=cfg.model,
            ctx=ctx,
            scenarios=scenarios,
            n_workers=cfg.execution.n_workers,
            resume=cfg.execution.resume,
            verbose=cfg.execution.verbose,
            workflow_name=cfg.execution.workflow.name,
            workflow_params=cfg.execution.workflow.params,
            extractors=cfg.execution.extractors,
        )

        print(
            f"Done: {result.n_success} succeeded, {result.n_failed} failed, "
            f"{result.n_skipped} skipped"
        )

        # Show individual case results if any failed
        if result.n_failed > 0:
            print("\n--- Failed Cases ---")
            for case_result in result.results:
                if not case_result.get("success"):
                    error_message = case_result.get("error", "Unknown error")
                    print(f"  {case_result.get('case_id')}: {error_message}")

        # Check logs
        log_dir = Path(ctx.root_dir) / "logs"
        if log_dir.exists():
            print(f"\nLogs available at: {log_dir}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
