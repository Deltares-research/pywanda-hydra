"""Example script demonstrating how to run scenarios using PyWandaHydra.

For production use, prefer the CLI::

    pywandahydra run config.yaml --workers 4 --resume
"""

import json
import os
import sys
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path

from pywandahydra.config.loader import RunMetadata
from pywandahydra.config.models import ModelSpecification, RunContext
from pywandahydra.execution.artifacts import create_run_directories
from pywandahydra.execution.runner import run
from pywandahydra.scenarios import load_scenarios
from pywandahydra.wanda.validation import assert_preflight_valid


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
    """Run scenarios from the examples data directory."""
    _print_startup_banner()

    data_dir = Path(__file__).parent / "data"

    # Load scenarios from Excel
    scenarios = load_scenarios(path=data_dir / "scenarios" / "cases.xls")

    # Model specification
    model_spec = ModelSpecification(
        model_path=data_dir / "model" / "base_model.wdi",
        wanda_bin=Path(r"c:\Program Files (x86)\Deltares\Wanda 4.8\Bin64"),
        base_model_name="base_model",
        run_steady=True,
        run_unsteady=True,
        reuse_existing_data=False,
    )

    # Validate all scenario references against the model before running.
    assert_preflight_valid(model_spec=model_spec, scenarios=scenarios)

    # Run context
    run_id = "eval_run_001"
    ctx = RunContext(
        run_id=run_id,
        root_dir=data_dir,
        timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
    )

    create_run_directories(ctx)
    run_metadata = RunMetadata()
    metadata_path = Path(ctx.root_dir) / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(run_metadata.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )

    # Execute all scenarios (sequential, with resume support)
    # Set verbose=True to enable detailed execution logging (for debugging)
    print(f"Running {len(scenarios)} scenarios with run ID '{run_id}'...")
    result = run(
        model=model_spec,
        ctx=ctx,
        scenarios=scenarios,
        n_workers=1,
        resume=True,
        verbose=False,  # Set to True for detailed execution logs
    )

    print(
        f"Done: {result.n_success} succeeded, {result.n_failed} failed, {result.n_skipped} skipped"
    )


if __name__ == "__main__":
    main()

