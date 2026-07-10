"""Scenario evaluation for the surge-vessel optimizer.

An *evaluation* maps a ``(number_of_vessels, c_value, laplace)`` triple to the
minimum pipeline pressure and minimum surge-vessel water level. The production
:class:`WandaEvaluator` realizes each evaluation as a normal single-scenario run
through the existing execution stack:

1. build a :class:`ScenarioSpecification` with parameter changes (vessel count,
   C-value, Laplace coefficient, plus any base parameters) and output specs for
   the vessel water level and the keyword-matched pipe pressures;
2. dispatch it through :func:`run_one_case` (model copy, simulation, extraction,
   caching, journaling). Identical triples reuse the cached case via the
   runner's resume mechanism, so repeated bisection probes are not re-simulated;
3. read the minimum pressure / water level back from the Parquet cache.

The :class:`Evaluator` protocol lets tests inject a synthetic evaluator so the
optimizer and bisection logic can be exercised without a WANDA installation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..config.models import ModelSpecification
from ..execution.case_plan import CasePlan
from ..execution.worker import run_one_case
from ..scenarios.schema import (
    ExportTableSpecification,
    ParameterChange,
    PostProcessingConfig,
    ScenarioMeta,
    ScenarioSpecification,
)
from .config import OptimizationConfig
from .metrics import read_min_metrics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvaluationResult:
    """Metrics obtained from a single optimization evaluation.

    Attributes:
        n_vessels: Number of surge vessels used.
        c_value: C-value applied (SI units).
        laplace: Laplace coefficient applied.
        min_pressure: Minimum pipeline pressure (SI units), or ``nan``.
        min_water_level: Minimum surge-vessel water level (SI units), or ``nan``.
        case_id: Identifier of the underlying case (empty for synthetic runs).
        failed: ``True`` if the simulation failed with a tolerated drainage
            outcome (the surge vessel emptied). Such a case is treated as
            unacceptable for water level (``min_water_level = -inf``) but
            acceptable for pressure (``min_pressure = +inf``), since drainage is a
            high-C / water-level limit rather than a pressure failure.
        error: The WANDA error message when ``failed`` is ``True``, else ``None``.
    """

    n_vessels: int
    c_value: float
    laplace: float
    min_pressure: float
    min_water_level: float
    case_id: str = ""
    failed: bool = False
    error: str | None = None


@runtime_checkable
class Evaluator(Protocol):
    """Maps a ``(n_vessels, c_value, laplace)`` triple to metrics."""

    def run(self, n_vessels: int, c_value: float, laplace: float) -> EvaluationResult:
        """Evaluate one triple and return the resulting metrics."""
        ...


def _classify_failure(error: str, patterns: list[str]) -> bool:
    """Return ``True`` if a failure ``error`` is a tolerated unacceptable outcome.

    A tolerated failure is one whose message contains any of ``patterns`` as a
    case-insensitive substring (e.g. a surge vessel draining, which WANDA reports
    as ``"Unsteady error in physical component: AIRVin A1 Empty"``). Such failures
    are physically meaningful *unacceptable* results, not fatal errors, so the
    optimizer records them as unacceptable and continues.

    Args:
        error: The WANDA error message.
        patterns: Case-insensitive substrings identifying tolerated failures.

    Returns:
        ``True`` if the error matches a tolerated pattern, else ``False``.
    """
    error_lower = error.lower()
    return any(pattern.lower() in error_lower for pattern in patterns)


def _case_id(n_vessels: int, c_value: float, laplace: float) -> str:
    """Deterministic, filesystem-safe case id for a triple.

    Identical triples map to the same id so the runner's resume mechanism can
    reuse a previously completed simulation.
    """
    return f"n{n_vessels:03d}_lap{laplace:g}_C{c_value:.6e}".replace("+", "").replace(".", "p")


def build_scenario(
    config: OptimizationConfig, n_vessels: int, c_value: float, laplace: float
) -> ScenarioSpecification:
    """Build the scenario for a single ``(n_vessels, c_value, laplace)`` evaluation.

    Args:
        config: The optimization configuration.
        n_vessels: Number of surge vessels.
        c_value: C-value to apply.
        laplace: Laplace coefficient to apply.

    Returns:
        A :class:`ScenarioSpecification` with the parameter changes and output
        specifications needed to read the minimum pressure / water level.
    """
    props = config.properties
    parameters: list[ParameterChange] = [
        *config.base_parameters,
        ParameterChange(component=config.surge_vessel, property=props.number, value=n_vessels),
        ParameterChange(component=config.surge_vessel, property=props.c_value, value=c_value),
        ParameterChange(component=config.surge_vessel, property=props.laplace, value=laplace),
    ]

    tables = [
        ExportTableSpecification(
            component=config.surge_vessel,
            property=config.water_level_property,
            mode="MIN",
        ),
        ExportTableSpecification(
            component=config.pressure_pipes_keyword,
            property=config.pressure_property,
            mode="MIN",
        ),
    ]

    case_id = _case_id(n_vessels, c_value, laplace)
    meta = ScenarioMeta.model_validate({"Number": n_vessels, "Include": True, "Name": case_id})
    return ScenarioSpecification(
        meta=meta,
        parameters=parameters,
        post_processing=PostProcessingConfig(tables=tables),
    )


class WandaEvaluator:
    """Production evaluator that runs scenarios through the execution stack."""

    def __init__(
        self,
        config: OptimizationConfig,
        run_root: Path,
        *,
        adapter_class: str = "pywandahydra.wanda.pywanda_adapter:PywandaAdapter",
    ) -> None:
        self._config = config
        self._run_root = Path(run_root)
        self._adapter_class = adapter_class
        # Unsteady simulation is required to observe the transient minima.
        self._model_spec: ModelSpecification = config.model.model_copy(
            update={"run_steady": True, "run_unsteady": True}
        )

    def run(self, n_vessels: int, c_value: float, laplace: float) -> EvaluationResult:
        """Run one evaluation and return the resulting metrics."""
        scenario = build_scenario(self._config, n_vessels, c_value, laplace)
        case_id = scenario.meta.name
        case_dir = self._run_root / "scenarios" / case_id
        plan = CasePlan(
            case_id=case_id,
            case_dir=case_dir,
            model_spec=self._model_spec,
            scenario=scenario,
            adapter_class=self._adapter_class,
        )

        result = run_one_case(plan)
        if not result.get("success"):
            error = str(result.get("error", "unknown error"))
            if _classify_failure(error, self._config.unacceptable_error_patterns):
                logger.warning(
                    "Evaluation %s failed with a tolerated drainage outcome; "
                    "treating it as unacceptable for water level (upper bound) but "
                    "acceptable for pressure, and continuing: %s",
                    case_id,
                    error,
                )
                # A drained ("Empty") vessel is a high-C / water-level limit, not a
                # pressure failure: -inf water level rejects it on the water-level
                # (upper-bound) criterion, while +inf pressure keeps the pressure
                # criterion monotonic in C so its lower bound is still found.
                return EvaluationResult(
                    n_vessels=n_vessels,
                    c_value=c_value,
                    laplace=laplace,
                    min_pressure=float("inf"),
                    min_water_level=float("-inf"),
                    case_id=case_id,
                    failed=True,
                    error=error,
                )
            raise RuntimeError(f"Evaluation {case_id} failed: {error}")

        min_pressure, min_water_level = read_min_metrics(
            case_dir,
            self._config.pressure_property,
            self._config.water_level_property,
        )
        return EvaluationResult(
            n_vessels=n_vessels,
            c_value=c_value,
            laplace=laplace,
            min_pressure=min_pressure,
            min_water_level=min_water_level,
            case_id=case_id,
        )
