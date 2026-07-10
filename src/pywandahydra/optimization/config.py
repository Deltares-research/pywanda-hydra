"""Configuration schema and loader for surge-vessel optimization.

The optimizer is driven by a single JSON input file that is parsed into an
:class:`OptimizationConfig`. It embeds the existing :class:`ModelSpecification`
and adds optimization-specific settings: which surge-vessel component and
properties to mutate, which pipes/property to check for minimum pressure, the
acceptance limits, the Laplace coefficients, the range of surge-vessel counts to
explore, the C-value bisection bracket, and convergence criteria.

Property names and acceptance-limit units are configurable so the exact WANDA
labels and unit conventions can be supplied without code changes. Acceptance
limits must be expressed in the SI units returned by the WANDA adapter
(e.g. Pa for pressure, m for water level).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..config.models import ModelSpecification
from ..scenarios.schema import ParameterChange


class VesselProperties(BaseModel):
    """Names of the surge-vessel properties the optimizer mutates."""

    model_config = ConfigDict(extra="forbid")

    number: str = Field(
        default="Number of vessels",
        description="Vessel property holding the number of surge vessels.",
    )
    c_value: str = Field(
        default="Initial C in P*V=C",
        description="Vessel property holding the mass-control C-value (C = p*V).",
    )
    laplace: str = Field(
        default="Laplace coefficient",
        description="Vessel property holding the Laplace (polytropic) coefficient.",
    )


class AcceptanceCriteria(BaseModel):
    """Acceptance limits (in adapter SI units)."""

    model_config = ConfigDict(extra="forbid")

    min_pressure: float = Field(
        ...,
        description="Minimum acceptable pipeline pressure (SI units, e.g. Pa).",
    )
    min_water_level: float = Field(
        ...,
        description="Minimum acceptable surge-vessel water level (SI units, e.g. m).",
    )


class LaplaceCoefficients(BaseModel):
    """Laplace coefficients used for each acceptance criterion."""

    model_config = ConfigDict(extra="forbid")

    water_level: float = Field(
        default=1.0,
        gt=0.0,
        description="Laplace coefficient for the minimum water-level criterion.",
    )
    pressure: float = Field(
        default=1.4,
        gt=0.0,
        description="Laplace coefficient for the minimum pressure criterion.",
    )


class VesselCountRange(BaseModel):
    """Inclusive range of surge-vessel counts to explore."""

    model_config = ConfigDict(extra="forbid")

    min: int = Field(..., ge=1, description="Smallest number of surge vessels.")
    max: int = Field(..., ge=1, description="Largest number of surge vessels.")
    step: int = Field(default=1, ge=1, description="Increment between counts.")

    @model_validator(mode="after")
    def _check_order(self) -> VesselCountRange:
        if self.max < self.min:
            raise ValueError("number_of_vessels.max must be >= number_of_vessels.min")
        return self

    def values(self) -> list[int]:
        """Return the ordered list of vessel counts to explore."""
        return list(range(self.min, self.max + 1, self.step))


class CValueBracket(BaseModel):
    """Bisection bracket for the C-value search."""

    model_config = ConfigDict(extra="forbid")

    lower: float = Field(..., gt=0.0, description="Lower C-value bound (SI units, e.g. J).")
    upper: float = Field(..., gt=0.0, description="Upper C-value bound (SI units, e.g. J).")

    @model_validator(mode="after")
    def _check_order(self) -> CValueBracket:
        if self.upper <= self.lower:
            raise ValueError("c_value.upper must be greater than c_value.lower")
        return self


class Convergence(BaseModel):
    """Bisection convergence criteria."""

    model_config = ConfigDict(extra="forbid")

    rel_tol: float = Field(
        default=0.01,
        gt=0.0,
        description="Stop when the new C-value deviates less than this fraction from the old.",
    )
    max_iter: int = Field(
        default=20,
        ge=1,
        description="Maximum bisection iterations per criterion.",
    )


class OptimizationConfig(BaseModel):
    """Top-level configuration for a surge-vessel optimization run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"),
        description="Unique run identifier.",
    )
    output_root: Path = Field(
        default=Path("./runs"),
        description="Root directory for optimization outputs.",
    )
    description: str | None = None

    model: ModelSpecification

    surge_vessel: str = Field(
        ...,
        description="Identifier or keyword of the inclined surge-vessel component.",
    )
    properties: VesselProperties = Field(default_factory=VesselProperties)

    pressure_pipes_keyword: str = Field(
        ...,
        description="Keyword selecting the pipes to check for minimum pressure.",
    )
    pressure_property: str = Field(
        default="Pressure",
        description="Pipe property whose minimum is checked.",
    )
    water_level_property: str = Field(
        default="Fluid level",
        description="Surge-vessel property whose minimum is checked.",
    )

    acceptance: AcceptanceCriteria
    laplace: LaplaceCoefficients = Field(default_factory=LaplaceCoefficients)
    number_of_vessels: VesselCountRange
    c_value: CValueBracket
    convergence: Convergence = Field(default_factory=Convergence)

    base_parameters: list[ParameterChange] = Field(
        default_factory=list,
        description="Parameter changes applied to every evaluation (e.g. flow scenario).",
    )
    n_workers: int = Field(default=1, ge=1)

    unacceptable_error_patterns: list[str] = Field(
        default_factory=lambda: ["Empty"],
        description=(
            "Case-insensitive substrings identifying WANDA simulation failures that "
            "are physically meaningful *unacceptable* outcomes rather than fatal "
            "errors (e.g. a surge vessel draining: 'AIRVin A1 Empty'). Matching "
            "failures are recorded as unacceptable evaluations (minima set to -inf) "
            "and the optimization continues; non-matching failures are re-raised."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_output_root(cls, data: object) -> object:
        if isinstance(data, dict) and "output_root" in data and data["output_root"] is not None:
            data = dict(data)
            data["output_root"] = Path(str(data["output_root"]).strip()).expanduser()
        return data


def load_optimization_config(path: Path | str) -> OptimizationConfig:
    """Load and validate an optimization configuration from a JSON file.

    Args:
        path: Path to the ``.json`` configuration file.

    Returns:
        Validated :class:`OptimizationConfig`.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unsupported or validation fails.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Optimization config not found: {path}")

    ext = path.suffix.lower()
    if ext != ".json":
        raise ValueError(f"Unsupported config format: '{ext}'. Use .json.")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a mapping, got: {type(raw).__name__}")

    return OptimizationConfig.model_validate(raw)


def validate_optimization_paths(config: OptimizationConfig, *, config_dir: Path) -> None:
    """Validate and resolve runtime-critical paths before running.

    Resolves relative paths against ``config_dir`` and updates ``config`` in place.

    Args:
        config: Validated optimization configuration.
        config_dir: Directory containing the configuration file.

    Raises:
        ValueError: If any path is invalid or not accessible.
    """
    model_path = config.model.model_path
    if not model_path.is_absolute():
        model_path = config_dir / model_path
    if model_path.suffix.lower() != ".wdi":
        raise ValueError(f"model.model_path must point to a .wdi file, got: {model_path}")
    if not model_path.exists():
        raise ValueError(f"model.model_path does not exist: {model_path}")

    wanda_bin = config.model.wanda_bin
    if not wanda_bin.is_absolute():
        wanda_bin = config_dir / wanda_bin
    if not wanda_bin.exists() or not wanda_bin.is_dir():
        raise ValueError(f"model.wanda_bin must be an existing directory: {wanda_bin}")

    output_root = config.output_root
    if not output_root.is_absolute():
        output_root = config_dir / output_root
    output_root.mkdir(parents=True, exist_ok=True)
    if not os.access(output_root, os.W_OK):
        raise ValueError(f"output_root is not writable: {output_root}")

    config.model.model_path = model_path
    config.model.wanda_bin = wanda_bin
    config.output_root = output_root
