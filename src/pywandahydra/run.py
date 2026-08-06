"""Public run preparation, validation, execution, and offline results API."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import ExecutionConfiguration, RunConfiguration, load_run_config
from .execution.case_execution import postprocess_case
from .execution.locking import RunLock
from .execution.outcomes import RunResult
from .execution.plans import CasePlan, ModelSpecification, RunPlan, build_case_plans
from .execution.result_extraction import requirements_from_scenario
from .execution.run_cases import run_cases
from .execution.run_directory import case_data_directory
from .execution.status import CaseStatus, CaseStatusStore
from .postprocessing.pipeline import process_run_results
from .results import ParquetResultStore
from .results.manifest import RunManifest, SourceFile, read_manifest, sha256_file, write_manifest
from .scenarios import ScenarioSpecification
from .scenarios.loader import load_scenario_document
from .scenarios.models.document import ScenarioDocument


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Validated run inputs, including the side-effect-free execution plan."""

    plan: RunPlan


@dataclass(frozen=True, slots=True)
class RunStatus:
    """Offline view of one manifest and the current status of its cases."""

    run_id: str
    run_dir: Path
    cases: tuple[CaseStatus | None, ...]


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
        upgrade=configuration.model.upgrade,
        run_steady=configuration.simulation.steady,
        run_unsteady=configuration.simulation.unsteady,
    )


def validate_run(config_path: Path | str, *, preflight: bool = False) -> ValidationReport:
    """Validate and prepare a configuration, optionally checking WANDA inputs."""
    return ValidationReport(prepare_run(config_path, preflight=preflight))


def _prepare_run_directory(plan: RunPlan) -> None:
    for name in ("figures", "inputs", "tables", "scenarios"):
        (plan.run_dir / name).mkdir(parents=True, exist_ok=True)
    sources = _copy_authored_inputs(plan)
    write_manifest(
        RunManifest.create(
            configuration=plan.configuration,
            scenario_document=plan.scenario_document,
            run_dir=plan.run_dir,
            sources=sources,
        )
    )


def _copy_authored_inputs(plan: RunPlan) -> tuple[SourceFile, ...]:
    inputs = plan.run_dir / "inputs"
    source_paths = (
        ("configuration", plan.config_path),
        ("scenarios", plan.scenario_document.source_path),
        ("model", plan.model_path),
    )
    sources: list[SourceFile] = []
    for category, source_path in source_paths:
        name = f"{category}/{source_path.name}"
        destination = inputs / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        sources.append(SourceFile(name=name, sha256=sha256_file(source_path)))
    return tuple(sources)


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


def read_run_status(run_dir: Path | str) -> RunStatus:
    """Read one run's manifest and case statuses without opening WANDA."""
    manifest = read_manifest(Path(run_dir))
    statuses = tuple(
        CaseStatusStore(manifest.run_dir / "scenarios" / scenario.name).read()
        for scenario in manifest.scenario_document.scenarios
        if scenario.include
    )
    return RunStatus(manifest.configuration.run_id, manifest.run_dir, statuses)


def postprocess_run(run_dir: Path | str, *, case_ids: set[str] | None = None) -> RunResult:
    """Regenerate configured outputs from committed results without simulating."""
    manifest = read_manifest(Path(run_dir))
    selected = tuple(
        scenario
        for scenario in manifest.scenario_document.scenarios
        if scenario.include and (case_ids is None or scenario.name in case_ids)
    )
    unknown = (case_ids or set()) - {scenario.name for scenario in selected}
    if unknown:
        raise ValueError(f"Unknown or excluded case IDs: {sorted(unknown)}")
    plans = _offline_case_plans(manifest, selected)
    _require_offline_stores(plans)
    with RunLock(manifest.run_dir):
        cases = tuple(postprocess_case(plan) for plan in plans)
        outcomes = process_run_results(
            run_root=manifest.run_dir,
            run_id=manifest.configuration.run_id,
        )
    return RunResult(manifest.configuration.run_id, cases, outcomes)


def _offline_model_specification(manifest: RunManifest) -> ModelSpecification:
    """Build a placeholder model specification that offline post-processing never opens."""
    return ModelSpecification(
        model_path=manifest.run_dir / "inputs" / "model" / manifest.configuration.model.path.name,
        wanda_bin=manifest.run_dir / "inputs",
        upgrade=manifest.configuration.model.upgrade,
        run_steady=manifest.configuration.simulation.steady,
        run_unsteady=manifest.configuration.simulation.unsteady,
    )


def _offline_case_plans(
    manifest: RunManifest, scenarios: tuple[ScenarioSpecification, ...]
) -> tuple[CasePlan, ...]:
    model_specification = _offline_model_specification(manifest)
    return tuple(
        CasePlan(
            case_id=scenario.name,
            case_dir=manifest.run_dir / "scenarios" / scenario.name,
            model_spec=model_specification,
            scenario=scenario,
            analysis_metadata=manifest.scenario_document.analysis_metadata,
            config_hash="manifest-v1",
        )
        for scenario in scenarios
    )


def _require_offline_stores(plans: tuple[CasePlan, ...]) -> None:
    for plan in plans:
        status = CaseStatusStore(plan.case_dir).read()
        store = ParquetResultStore(case_data_directory(plan.case_dir))
        if status is None or status.simulation_status != "succeeded":
            raise ValueError(
                f"Case {plan.case_id} has no successful simulation; resume or simulate it first."
            )
        inventory = store.inventory()
        if inventory is None or not inventory.satisfies(requirements_from_scenario(plan.scenario)):
            raise ValueError(
                f"Case {plan.case_id} has incomplete result data; resume or simulate it first."
            )
