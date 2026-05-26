"""Example script demonstrating how to run scenarios using PyWandaHydra.

For production use, prefer the CLI::

    pywandahydra run config.yaml --workers 4 --resume
"""

from datetime import datetime
from pathlib import Path

from pywandahydra.config.models import ModelSpecification, RunContext
from pywandahydra.execution.runner import run
from pywandahydra.scenarios.mapper import load_scenarios


def main() -> None:
    """Run scenarios from the test_data directory."""
    run_dir = Path(__file__).parents[1] / "test_data" / "execution"

    # Load scenarios from Excel
    scenarios = load_scenarios(path=run_dir / "parameters" / "cases.xls")

    # Model specification
    model_spec = ModelSpecification(
        model_path=run_dir / "model" / "base_model.wdi",
        wanda_bin=r"c:\Program Files (x86)\Deltares\Wanda 4.7\Bin\\",
        base_model_name="base_model",
        run_steady=True,
        run_unsteady=True,
        readonly=False,
    )

    # Run context
    run_id = "eval_run_001"
    ctx = RunContext(
        run_id=run_id,
        root_dir=str(run_dir),
        timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
    )

    # Execute all scenarios (sequential, with resume support)
    result = run(
        model=model_spec,
        ctx=ctx,
        scenarios=scenarios,
        n_workers=1,
        resume=True,
    )

    print(
        f"Done: {result.n_success} succeeded, {result.n_failed} failed, "
        f"{result.n_skipped} skipped"
    )


if __name__ == "__main__":
    main()
