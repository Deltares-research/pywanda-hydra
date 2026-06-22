"""Example: Percentile pressure table — Extractor + CaseStep.

Extracts the minimum pressure per pipe for a set of keyword groups while
the WANDA model session is still open, then produces a per-case Excel
workbook listing the pipes that fall at or below a given pressure percentile.

Two plugins are defined:

``PercentilePressureExtractor``
    Runs during model execution, before the WANDA session closes.  For each
    configured keyword it finds all eligible pipes, reads the extreme-minimum
    pressure vector (``get_extr_min_pipe``), converts to model units, and
    records the minimum value together with its location along the pipe.
    The results are stored in the standard Parquet cache so post-processing
    can access them without reopening the model.

``PercentilePressureTableStep``
    CaseStep that reads the cached per-keyword DataFrames, applies the
    requested percentile threshold, and writes an Excel workbook with one
    sheet per keyword (pipes at or below the threshold) plus a summary sheet.

--- Plugin registration (pyproject.toml) ---

    [project.entry-points."pywandahydra.extractors"]
    percentile_pressure = "my_plugin.steps:PercentilePressureExtractor"

    [project.entry-points."pywandahydra.case_steps"]
    percentile_pressure_table = "my_plugin.steps:PercentilePressureTableStep"

--- YAML config ---

    execution:
      extractors:
        - name: percentile_pressure
          params:
            keywords: [PALL]

      workflow:
        name: composed
        params:
          case_steps:
            - name: percentile_pressure_table
              params:
                keywords: [PALL]
                percentile: 5
                output_filename: percentile_pressures
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from pywandahydra.config.loader import RunMetadata
from pywandahydra.config.models import ModelSpecification, RunContext
from pywandahydra.execution.artifacts import create_run_directories
from pywandahydra.execution.runner import run as run_scenarios
from pywandahydra.postprocessing.core.context import (
    CaseContext,
    ExtractionContext,
    PostProcessingRunContext,
)
from pywandahydra.postprocessing.core.protocols import CaseStep, RunStep
from pywandahydra.postprocessing.extraction.extractors import Extractor, register_extractor
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.scenarios.mapper import load_scenarios
from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification

logger = logging.getLogger(__name__)

_EXTRACTOR_NAME = "percentile_pressure"


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class PercentilePressureExtractor(Extractor):
    """Extractor: collect per-pipe minimum pressures grouped by keyword.

    Runs while the WANDA model session is open and caches the results so
    that post-processing does not require the model to be reopened.

    For each keyword the extractor finds all eligible pipes (not disused,
    ``is_pipe() == True``), reads the ``Pressure`` property's
    extreme-minimum vector, converts to model units, and records the minimum
    value together with the location along the pipe at which it occurs.

    The results are stored as a nested custom cache entry (one Parquet file
    per keyword under ``custom/percentile_pressure/``).
    """

    name: ClassVar[str] = _EXTRACTOR_NAME
    description: ClassVar[str] = "Collect per-pipe minimum pressures for each keyword group."

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

        keywords: list[str] = Field(
            default_factory=lambda: [],
            description="WANDA component keyword tags used to group pipes.",
        )

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def extract(self, ctx: ExtractionContext) -> dict[str, Any]:
        results: dict[str, pd.DataFrame] = {}
        for keyword in self._p.keywords:
            df = _extract_pipe_pressures(ctx.model, keyword)
            if df.empty:
                logger.warning(
                    "No eligible pipes found for keyword '%s' in case '%s'.",
                    keyword,
                    ctx.case_id,
                )
                continue
            results[keyword] = df
        return results


def _extract_pipe_pressures(model: Any, keyword: str) -> pd.DataFrame:
    """Return a DataFrame of per-pipe minimum pressures for *keyword*.

    Columns
    -------
    component : str
        Full WANDA component name.
    min_pressure : float
        Minimum pressure over all time steps, in model units.
    location_m : float
        Distance along the pipe (m) at which the minimum occurs.

    Rows are sorted in ascending order of ``min_pressure`` (lowest first).
    """
    if keyword.upper() == "PALL":
        pipes = model.get_all_pipes()
    else:
        pipes = model.get_components_with_keyword(keyword)

    records: list[dict[str, Any]] = []
    unit_factor: float | None = None

    for pipe in pipes:
        if pipe.is_disused():
            continue
        if not pipe.is_pipe():
            continue

        pressure_prop = pipe.get_property("Pressure")
        extr_min = np.asarray(pressure_prop.get_extr_min_pipe(), dtype=float)

        if unit_factor is None:
            unit_factor = float(pressure_prop.get_unit_factor())

        n_elements: int = pressure_prop.get_number_of_elements()
        pipe_length: float = pipe.get_property("Length").get_scalar_float()
        dx: float = pipe_length / n_elements if n_elements > 0 else 0.0

        min_idx = int(np.argmin(extr_min))
        records.append(
            {
                "component": pipe.get_complete_name_spec(),
                "min_pressure": float(extr_min[min_idx]) * (unit_factor or 1.0),
                "location_m": min_idx * dx,
            }
        )

    if not records:
        return pd.DataFrame(columns=["component", "min_pressure", "location_m"])

    df = pd.DataFrame(records)
    return df.sort_values("min_pressure").reset_index(drop=True)


# ---------------------------------------------------------------------------
# CaseStep
# ---------------------------------------------------------------------------


class PercentilePressureTableStep(CaseStep):
    """CaseStep: write a percentile pressure table from cached extractor data.

    Reads the per-keyword DataFrames written by
    :class:`PercentilePressureExtractor` and produces an Excel workbook with:

    - **Summary** sheet — one row per keyword with the percentile threshold,
      total pipe count, count below the threshold, and mean pressure of the
      pipes below the threshold.
    - One sheet per keyword — component name, minimum pressure, and the
      location along the pipe where the minimum occurs, for all pipes at or
      below the threshold.

    Output: ``<case_dir>/tables/<output_filename>.xlsx``.
    """

    name: ClassVar[str] = "percentile_pressure_table"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

        keywords: list[str] = Field(
            default_factory=lambda: ["MC", "PSUC", "NORO", "PGRP"],
            description=(
                "Keyword groups to include.  Must match the keywords configured in the extractor."
            ),
        )
        percentile: float = Field(
            default=5.0,
            ge=0.0,
            le=100.0,
            description=(
                "Pressure percentile threshold.  Pipes whose minimum pressure "
                "falls at or below this percentile are listed per keyword."
            ),
        )
        output_filename: str = Field(
            default="percentile_pressures",
            description="Stem of the output Excel file (no extension).",
        )

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def applicable(self, ctx: CaseContext) -> bool:
        return _EXTRACTOR_NAME in ctx.cache.list_custom_extractors()

    def run(self, ctx: CaseContext) -> None:
        raw = ctx.cache.read_custom(_EXTRACTOR_NAME)
        if isinstance(raw, pd.DataFrame):
            logger.warning(
                "Expected nested dict from '%s' extractor but got a plain DataFrame; "
                "re-run the extractor or check the cache layout.",
                _EXTRACTOR_NAME,
            )
            return

        per_keyword: dict[str, pd.DataFrame] = raw  # type: ignore[assignment]
        summary_rows: list[dict[str, Any]] = []
        keyword_tables: dict[str, pd.DataFrame] = {}

        for keyword in self._p.keywords:
            if keyword not in per_keyword:
                logger.warning("No cached data for keyword '%s' — skipped.", keyword)
                continue

            df = per_keyword[keyword].copy()
            threshold = float(np.percentile(df["min_pressure"], self._p.percentile))
            df_below = df[df["min_pressure"] <= threshold].copy()

            df_below = df_below.rename(
                columns={
                    "component": "Component",
                    "min_pressure": "Min pressure",
                    "location_m": "Location (m)",
                }
            )
            df_below["Min pressure"] = df_below["Min pressure"].round(4)
            df_below["Location (m)"] = df_below["Location (m)"].round(2)

            keyword_tables[keyword] = df_below
            summary_rows.append(
                {
                    "Keyword": keyword,
                    f"P{self._p.percentile:.0f} threshold": round(threshold, 4),
                    "Pipe count (total)": len(df),
                    f"Pipe count (≤ P{self._p.percentile:.0f})": len(df_below),
                    "Mean pressure at percentile": round(float(df_below["Min pressure"].mean()), 4),
                }
            )

        if not keyword_tables:
            logger.warning(
                "No keyword data available for case '%s'; table not written.",
                ctx.case_dir.name,
            )
            return

        tables_dir = ctx.case_dir / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)
        out_path = tables_dir / f"{self._p.output_filename}.xlsx"

        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            summary_df = pd.DataFrame(summary_rows).set_index("Keyword")
            summary_df.to_excel(writer, sheet_name="Summary")
            for keyword, df_kw in keyword_tables.items():
                df_kw.to_excel(writer, sheet_name=keyword[:31], index=False)

        logger.info("Percentile pressure table written to %s", out_path)


# ---------------------------------------------------------------------------
# RunStep
# ---------------------------------------------------------------------------


class PercentilePressureAggregateStep(RunStep):
    """RunStep: aggregate per-case percentile summaries into a run-level table.

    After :class:`PercentilePressureTableStep` has written one Excel workbook
    per case, this step collects the **Summary** sheet from every case, prepends
    a ``case`` column, and writes a single consolidated table to
    ``<run_root>/tables/<output_filename>.xlsx``.

    This is the percentile-pressure equivalent of ``AggregateTablesStep``,
    which aggregates the standard min/max summary tables.

    --- Plugin registration (pyproject.toml) ---

        [project.entry-points."pywandahydra.run_steps"]
        percentile_pressure_aggregate = "my_plugin.steps:PercentilePressureAggregateStep"

    --- YAML workflow config ---

        execution:
          workflow:
            name: composed
            params:
              run_steps:
                - name: percentile_pressure_aggregate
                  params:
                    case_filename: percentile_pressures
                    output_filename: aggregated_percentile_pressures
    """

    name: ClassVar[str] = "percentile_pressure_aggregate"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

        case_filename: str = Field(
            default="percentile_pressures",
            description=(
                "Stem of the per-case Excel file written by PercentilePressureTableStep "
                "(no extension)."
            ),
        )
        output_filename: str = Field(
            default="aggregated_percentile_pressures",
            description="Stem of the run-level output Excel file (no extension).",
        )

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def run(self, ctx: PostProcessingRunContext) -> None:
        scenarios_dir = ctx.run_root / "scenarios"
        frames: list[pd.DataFrame] = []

        for case_dir in sorted(scenarios_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            xlsx_path = case_dir / "tables" / f"{self._p.case_filename}.xlsx"
            if not xlsx_path.exists():
                logger.warning("No percentile table found for case '%s' — skipped.", case_dir.name)
                continue
            summary_df = pd.read_excel(xlsx_path, sheet_name="Summary", index_col=0)
            summary_df.insert(0, "case", case_dir.name)
            frames.append(summary_df)

        if not frames:
            logger.warning("No per-case percentile tables found; aggregate not written.")
            return

        result = pd.concat(frames)
        result.index.name = "Keyword"

        tables_dir = ctx.run_root / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)
        out_path = tables_dir / f"{self._p.output_filename}.xlsx"
        result.to_excel(out_path, engine="openpyxl")

        logger.info("Aggregated percentile table written to %s", out_path)


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------


def _load_case_context(case_dir: Path, case_number: int) -> CaseContext:
    """Build a minimal CaseContext from a case directory on disk."""
    case_id = case_dir.name
    state_path = case_dir / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        case_id = state.get("case_id", case_id)
    scenario = ScenarioSpecification(
        meta=ScenarioMeta.model_validate({"Number": case_number, "Include": True, "Name": case_id})
    )
    return CaseContext(cache=ParquetCache(case_dir), scenario=scenario, case_dir=case_dir)


def main() -> None:
    """Run the example model with the extractor enabled, then write percentile tables.

    The extractor is registered programmatically so the entry-point plugin
    mechanism is not required for this standalone script.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    data_dir = Path(__file__).parent / "data"
    keywords = ["PALL"]
    run_id = "example_run_percentile"
    run_root = data_dir / "runs" / run_id

    # Register so resolve_extractor() can find it by name during the run.
    register_extractor(PercentilePressureExtractor)

    scenarios = load_scenarios(path=data_dir / "scenarios" / "cases.xls")
    model_spec = ModelSpecification(
        model_path=data_dir / "model" / "base_model.wdi",
        wanda_bin=Path(r"c:\Program Files (x86)\Deltares\Wanda 4.8\Bin64"),
        base_model_name="base_model",
        run_steady=True,
        run_unsteady=True,
        reuse_existing_data=False,
    )

    ctx = RunContext(
        run_id=run_id,
        root_dir=run_root,
        timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
    )
    create_run_directories(ctx)

    run_metadata = RunMetadata()
    metadata_path = run_root / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(run_metadata.model_dump(), indent=2, default=str), encoding="utf-8"
    )

    result = run_scenarios(
        model=model_spec,
        ctx=ctx,
        scenarios=scenarios,
        n_workers=1,
        resume=True,
        extractors=[{"name": _EXTRACTOR_NAME, "params": {"keywords": keywords}}],
    )
    print(f"Run complete: {result.n_success} succeeded, {result.n_failed} failed")

    # Apply the CaseStep to each case directory that has cached extractor data.
    step = PercentilePressureTableStep(
        PercentilePressureTableStep.Params(
            keywords=keywords,
            percentile=5,
            output_filename="percentile_pressures",
        )
    )

    scenarios_dir = run_root / "scenarios"
    for i, case_dir in enumerate(sorted(scenarios_dir.iterdir()), start=1):
        if not case_dir.is_dir():
            continue
        case_ctx = _load_case_context(case_dir, case_number=i)
        if step.applicable(case_ctx):
            step.run(case_ctx)
            print(f"Table written for {case_dir.name}")
        else:
            print(f"Skipping {case_dir.name}: extractor data not in cache.")

    # Aggregate all per-case summaries into a single run-level table.
    aggregate_step = PercentilePressureAggregateStep(
        PercentilePressureAggregateStep.Params(
            case_filename="percentile_pressures",
            output_filename="aggregated_percentile_pressures",
        )
    )
    run_ctx = PostProcessingRunContext(
        run_root=run_root,
        run_id=run_id,
        case_results=(),
    )
    aggregate_step.run(run_ctx)
    out = run_root / "tables" / "aggregated_percentile_pressures.xlsx"
    print(f"Aggregated table written to {out}")


if __name__ == "__main__":
    main()
