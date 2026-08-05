"""Public run preparation, validation, and execution API."""

from __future__ import annotations

import json
from pathlib import Path

from .config import ExecutionConfiguration, RunConfiguration, load_run_config
from .execution.locking import RunLock
from .execution.outcomes import RunResult
from .execution.plans import ModelSpecification, RunPlan, build_case_plans
from .execution.run_cases import run_cases
from .postprocessing.pipeline import process_run_results
from .scenarios.loader import load_scenario_document
from .scenarios.models.document import ScenarioDocument


def _resolve(path: Path, base_dir: Path) -> Path:
    return path if path.is_absolute() else (base_dir / path).resolve()


def _validate_paths(
    configuration: RunConfiguration, config_path: Path
) -> tuple[Path, Path, Path, Path]:
    base_dir = config_path.parent
    model_path = _resolve(configuration.model.path, base_dir)
    wanda_bin = _resolve(configuration.model.wanda_bin, base_dir)
    scenario_path = _resolve(configuration.scenario_file, base_dir)
    run_dir = _resolve(configuration.output_root, base_dir) / configuration.run_id

    if model_path.suffix.lower() != ".wdi":
        raise ValueError(f"model.path must point to a .wdi file, got: {model_path}")
    if not model_path.is_file():
        raise ValueError(f"model.path does not exist: {model_path}")
    if not wanda_bin.is_dir():
        raise ValueError(f"model.wanda_bin must be an existing directory: {wanda_bin}")
    if not scenario_path.is_file():
        raise ValueError(f"scenario_file does not exist: {scenario_path}")
    return model_path, wanda_bin, scenario_path, run_dir


def _legacy_model(plan: RunPlan) -> ModelSpecification:
    return ModelSpecification(
        model_path=plan.model_path,
        wanda_bin=plan.wanda_bin,
        base_model_name=plan.model_path.stem,
        upgrade=plan.configuration.model.upgrade,
        run_steady=plan.configuration.simulation.steady,
        run_unsteady=plan.configuration.simulation.unsteady,
    )


def _validate_case_names(document: ScenarioDocument) -> None:
    names = [scenario.name for scenario in document.scenarios if scenario.include]
    invalid = [name for name in names if not name or Path(name).name != name or name in {".", ".."}]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if invalid:
        raise ValueError(f"Included case names must be safe path names: {invalid}")
    if duplicates:
        raise ValueError(f"Included case names must be unique: {duplicates}")


def prepare_run(
    config_path: Path | str,
    *,
    workers: int | None = None,
    resume: bool | None = None,
    preflight: bool = False,
) -> RunPlan:
    """Load and prepare a run without creating model copies or output files."""
    resolved_config_path = Path(config_path).expanduser().resolve()
    configuration = load_run_config(resolved_config_path)
    execution: ExecutionConfiguration = configuration.execution
    if workers is not None:
        execution = execution.model_copy(update={"workers": workers})
    if resume is not None:
        execution = execution.model_copy(update={"resume": resume})
    if execution != configuration.execution:
        configuration = configuration.model_copy(update={"execution": execution})

    model_path, wanda_bin, scenario_path, run_dir = _validate_paths(
        configuration, resolved_config_path
    )
    document = load_scenario_document(scenario_path)
    _validate_case_names(document)
    legacy_model = _legacy_model_stub(configuration, model_path, wanda_bin)
    cases = tuple(
        build_case_plans(
            legacy_model,
            list(document.scenarios),
            run_dir,
            analysis_metadata=document.analysis_metadata,
        )
    )
    plan = RunPlan(
        configuration=configuration,
        config_path=resolved_config_path,
        model_path=model_path,
        wanda_bin=wanda_bin,
        run_dir=run_dir,
        scenario_document=document,
        cases=cases,
    )
    if preflight:
        from .wanda.validation import assert_preflight_valid

        assert_preflight_valid(model_spec=_legacy_model(plan), scenarios=list(document.scenarios))
    return plan


def _legacy_model_stub(
    configuration: RunConfiguration, model_path: Path, wanda_bin: Path
) -> ModelSpecification:
    return ModelSpecification(
        model_path=model_path,
        wanda_bin=wanda_bin,
        base_model_name=model_path.stem,
        upgrade=configuration.model.upgrade,
        run_steady=configuration.simulation.steady,
        run_unsteady=configuration.simulation.unsteady,
    )


def validate_run(config_path: Path | str, *, preflight: bool = False) -> RunPlan:
    """Validate and prepare a configuration, optionally checking WANDA inputs."""
    return prepare_run(config_path, preflight=preflight)


def _prepare_run_directory(plan: RunPlan) -> None:
    for name in ("figures", "logs", "tables", "scenarios"):
        (plan.run_dir / name).mkdir(parents=True, exist_ok=True)
    log_path = plan.run_dir / "logs" / "run.json"
    log_path.write_text(
        json.dumps(
            {
                "configuration": plan.configuration.model_dump(mode="json"),
                "config_path": str(plan.config_path),
                "scenarios": [
                    scenario.model_dump(mode="json")
                    for scenario in plan.scenario_document.scenarios
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def execute_run(plan: RunPlan) -> RunResult:
    """Execute a prepared plan with explicit recovery-aware case actions."""
    with RunLock(plan.run_dir):
        _prepare_run_directory(plan)
        cases = run_cases(plan.cases, plan.configuration.execution.workers)
        outcomes = process_run_results(
            run_root=plan.run_dir,
            run_id=plan.configuration.run_id,
        )
    return RunResult(
        run_id=plan.configuration.run_id,
        cases=cases,
        post_processing=outcomes,
    )
