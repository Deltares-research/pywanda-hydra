"""Example script demonstrating how to run scenarios using PyWandaHydra.

For production use, prefer the CLI::

    pywandahydra run config.yaml --workers 4 --resume
"""

import os
import sys
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path

from pywandahydra.config.models import ModelSpecification, RunContext
from pywandahydra.execution.runner import run
from pywandahydra.scenarios.mapper import load_scenarios
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
        "pywandahydra.location: "
        f"{pywandahydra_spec.origin if pywandahydra_spec else 'NOT FOUND'}"
    )
    print(
        "pywanda.location: " f"{pywanda_spec.origin if pywanda_spec else 'NOT FOUND'}"
    )
    print("===================================")


def main() -> None:
    """Run scenarios from the test_data directory."""
    _print_startup_banner()

    run_dir = Path(__file__).parents[1] / "test_data" / "execution"

    # Load scenarios from Excel
    scenarios = load_scenarios(path=run_dir / "parameters" / "cases.xls")

    # Model specification
    model_spec = ModelSpecification(
        model_path=run_dir / "model" / "base_model.wdi",
        wanda_bin=Path(r"c:\Program Files (x86)\Deltares\Wanda 4.8\Bin64"),
        base_model_name="base_model",
        run_steady=True,
        run_unsteady=True,
        readonly=False,
    )

    # Validate all scenario references against the model before running.
    assert_preflight_valid(model_spec=model_spec, scenarios=scenarios)

    # Run context
    run_id = "eval_run_001"
    ctx = RunContext(
        run_id=run_id,
        root_dir=run_dir,
        timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
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
        f"Done: {result.n_success} succeeded, {result.n_failed} failed, "
        f"{result.n_skipped} skipped"
    )


if __name__ == "__main__":
    main()
