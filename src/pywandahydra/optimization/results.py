"""Result data structures and JSON/CSV writers for the optimizer."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .bisection import BoundType


@dataclass(frozen=True)
class CriterionBoundary:
    """Bisection outcome for a single acceptance criterion.

    Attributes:
        criterion: ``"pressure"`` or ``"water_level"``.
        laplace: Laplace coefficient used for this criterion.
        boundary: C-value at the acceptability boundary, or ``None``.
        bound_type: How the criterion constrains the C-value.
        converged: Whether the bisection converged to the tolerance.
        iterations: Number of bisection iterations performed.
    """

    criterion: str
    laplace: float
    boundary: float | None
    bound_type: BoundType
    converged: bool
    iterations: int


@dataclass(frozen=True)
class VesselResult:
    """Feasible C-range for one surge-vessel count.

    Attributes:
        n_vessels: Number of surge vessels.
        pressure: Pressure-criterion bisection outcome (Laplace 1.4).
        water_level: Water-level-criterion bisection outcome (Laplace 1.0).
        c_lower: Lower edge of the feasible C-range, or ``None``.
        c_upper: Upper edge of the feasible C-range, or ``None``.
        feasible: Whether a non-empty acceptable C-range exists.
    """

    n_vessels: int
    pressure: CriterionBoundary
    water_level: CriterionBoundary
    c_lower: float | None
    c_upper: float | None
    feasible: bool


@dataclass(frozen=True)
class OptimizationResults:
    """Aggregated optimization results across all vessel counts.

    Attributes:
        run_id: The optimization run identifier.
        vessels: Per-vessel-count results, ordered by count.
        min_feasible_vessels: Smallest number of vessels with a feasible
            C-range, or ``None`` if no count is feasible.
    """

    run_id: str
    vessels: list[VesselResult] = field(default_factory=list)
    min_feasible_vessels: int | None = None

    def to_records(self) -> list[dict]:
        """Flatten per-vessel results to CSV-friendly row dicts."""
        rows: list[dict] = []
        for v in self.vessels:
            rows.append(
                {
                    "n_vessels": v.n_vessels,
                    "c_lower": v.c_lower,
                    "c_upper": v.c_upper,
                    "feasible": v.feasible,
                    "pressure_boundary": v.pressure.boundary,
                    "pressure_bound_type": v.pressure.bound_type,
                    "pressure_converged": v.pressure.converged,
                    "pressure_iterations": v.pressure.iterations,
                    "water_level_boundary": v.water_level.boundary,
                    "water_level_bound_type": v.water_level.bound_type,
                    "water_level_converged": v.water_level.converged,
                    "water_level_iterations": v.water_level.iterations,
                }
            )
        return rows


def write_json(results: OptimizationResults, path: Path) -> None:
    """Write the full optimization results to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": results.run_id,
        "min_feasible_vessels": results.min_feasible_vessels,
        "vessels": [asdict(v) for v in results.vessels],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(results: OptimizationResults, path: Path) -> None:
    """Write the per-vessel-count summary to a CSV file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "n_vessels",
        "c_lower",
        "c_upper",
        "feasible",
        "pressure_boundary",
        "pressure_bound_type",
        "pressure_converged",
        "pressure_iterations",
        "water_level_boundary",
        "water_level_bound_type",
        "water_level_converged",
        "water_level_iterations",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results.to_records())
