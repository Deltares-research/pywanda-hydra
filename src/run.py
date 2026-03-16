"""Example script to run scenarios using PyWandaHydra."""

from datetime import datetime
from pathlib import Path

from pywandahydra.config.models import ModelSpecification, RunContext
from pywandahydra.execution.artifacts import create_run_directories, write_run_log
from pywandahydra.scenarios.mapper import load_scenarios
from pywandahydra.wanda.api import apply_parameter_change
from pywandahydra.wanda.create_scenario import prepare_scenario_model
from pywandahydra.wanda.session import wanda_session


def main() -> None:
    """Main function to run scenarios."""
    # Define run_path
    run_dir = Path(__file__).parents[1] / "test_data" / "execution"

    # Load scenarios
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

    # Run context manager
    run_id = "eval_run_001"
    model_context = RunContext(
        run_id=run_id,
        root_dir=run_dir,
        timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
    )

    # Create run directories and write log
    create_run_directories(model_context)
    write_run_log(context_object=model_context, model_spec=model_spec, scenarios=scenarios)

    # Loop through scenarios and print their names
    for scenario in scenarios:
        print(f"Loaded scenario: {scenario.meta.name}")
        # Prepare scenario-specific model
        scenario_model_path = prepare_scenario_model(
            base_model_path=model_spec.model_path,
            scenario_dir=Path(model_context.root_dir) / "scenarios",
            scenario_name=scenario.meta.name,
            readonly=model_spec.readonly,
        )
        # Open WANDA session and run scenario (commented out for this example)
        with wanda_session(
            spec=model_spec,
            model_path=scenario_model_path,
        ) as model:
            # Apply general parameter changes
            for change in model_spec.global_overrides:
                apply_parameter_change(model, change)

            # Apply scenario-specific parameter changes
            for change in scenario.parameters:
                apply_parameter_change(model, change)

            model.save_model_input()
            # Run steady simulation if specified
            if model_spec.run_steady:
                model.run_steady()

            # Run unsteady simulation if specified
            if (
                model_spec.run_unsteady
                and model.get_property("Simulation time").get_scalar_float() > 0
            ):
                model.run_unsteady()

    # # For this example, run ONLY the first scenario
    # scenario = scenarios[0]

    # print(f"Running scenario: {scenario.meta.name}")

    # # ------------------------------------------------------------------
    # # 2. Define model specification (serializable)
    # # ------------------------------------------------------------------
    # model_spec = ModelSpecification(
    #     model_path="model/base_model.wdi",
    #     wanda_bin="C:/Program Files/WANDA/bin",  # adjust for your system
    #     run_steady=True,
    #     run_unsteady=True,
    #     global_overrides=[],  # optional
    # )

    # # ------------------------------------------------------------------
    # # 3. Create run context (serializable)
    # # ------------------------------------------------------------------
    # run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    # run_root = Path("runs") / run_id

    # ctx = RunContext(
    #     run_id=run_id,
    #     root_dir=str(run_root),
    #     analysis=scenario.analysis,
    #     meta={
    #         "source_file": "parameters/cases.xlsx",
    #         "model": "base_model.wdi",
    #     },
    # )

    # # Create folder structure and persist metadata
    # create_run_layout(ctx)

    # # ------------------------------------------------------------------
    # # 4. Open model and execute scenario
    # # ------------------------------------------------------------------
    # scenario_dir = run_root / "scenarios" / scenario.meta.name
    # scenario_dir.mkdir(parents=True, exist_ok=True)

    # with wanda_session(model_spec) as model:
    #     # --- Apply global overrides (none in this example) ---
    #     for change in model_spec.global_overrides:
    #         apply_parameter_change(model, change)

    #     # --- Apply scenario parameter changes ---
    #     for change in scenario.parameters:
    #         apply_parameter_change(model, change)

    #     # --- Run model ---
    #     if model_spec.run_steady:
    #         model.save_model_input()
    #         model.run_steady()

    #     if model_spec.run_unsteady:
    #         sim_time = model.get_property("Simulation time").get_scalar_float()
    #         if sim_time > 0:
    #             model.run_unsteady()

    # print(f"Scenario '{scenario.meta.name}' completed.")
    # print(f"Results stored in: {scenario_dir}")


if __name__ == "__main__":
    main()
#    main()
#    main()
