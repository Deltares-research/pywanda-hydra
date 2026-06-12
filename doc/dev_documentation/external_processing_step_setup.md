# External Processing Step Setup Guide

This guide shows how to add a custom processing step from another package (outside this repository) and make it discoverable by pywandahydra.

## What Can Be Extended

pywandahydra discovers plugins via Python entry points.

Supported groups:

- `pywandahydra.case_steps`: case-level postprocessing steps
- `pywandahydra.run_steps`: run-level postprocessing steps
- `pywandahydra.workflows`: workflows that assemble steps
- `pywandahydra.themes`: plotting themes
- `pywandahydra.scenario_sources`: scenario input loaders

For cross-case analysis and comparison figures, use a `run_step`.

### Related Guides

- **[custom_extractors.md](custom_extractors.md)** â€“ Create custom extractors to pull additional model data during execution (more powerful than case steps; recommended for accessing live model).
- **[case_step_data_export.md](case_step_data_export.md)** â€“ Use case steps to export derived metrics from already-cached data, preparing for run-step aggregation.
- **Extending extraction** â€“ See the "Extending Extracted Data" section in [case_step_data_export.md](case_step_data_export.md#extending-extracted-data).

## 1. Create a Separate Python Package

Example package structure:

```text
my-hydra-plugins/
  pyproject.toml
  my_hydra_plugins/
    __init__.py
    run_steps.py
    workflow.py
```

  ## 2. Implement a Cross-Case Run Step (Comparison + Plot)

  Run steps receive a `PostProcessingRunContext` and can read all case outputs from one run.

  Create a class with:

- class attribute `name: str`
- nested pydantic model `Params`
  - method `run(ctx)`

  Example (`my_hydra_plugins/run_steps.py`):

```python
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from pydantic import BaseModel, ConfigDict


  class CompareCasesPressureStep:
    """Build a cross-case table and plot from per-case summary tables."""

    name = "compare_cases_pressure"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        property_name: str = "Pressure"
        mode: str = "MAX"
        output_basename: str = "cross_case_pressure"

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def run(self, ctx) -> None:
        cenarios_dir = ctx.run_root / "scenarios"
        out_dir = ctx.run_root / "comparisons"
        out_dir.mkdir(parents=True, exist_ok=True)

        rows: list[dict[str, object]] = []
        for case_result in ctx.case_results:
            if case_result.get("success") is not True:
            continue

            case_id = str(case_result["case_id"])
            table_path = scenarios_dir / case_id / "summary_table.csv"
            if not table_path.exists():
            continue

            df = pd.read_csv(table_path)
            filt = (
            (df["property"] == self._p.property_name)
            & (df["mode"] == self._p.mode)
            )
            if not filt.any():
            continue

            value = float(df.loc[filt, "value"].iloc[0])
            rows.append({"case": case_id, "value": value})

        result = pd.DataFrame(rows).sort_values("case")
        csv_out = out_dir / f"{self._p.output_basename}.csv"
        png_out = out_dir / f"{self._p.output_basename}.png"
        result.to_csv(csv_out, index=False)

        if not result.empty:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(
                result["case"], 
                result["value"], 
                marker="o", 
                linestyle="-"
            )
            ax.set_xlabel("Case")
            ax.set_ylabel(f"{self._p.property_name} ({self._p.mode})")
            ax.set_title("Cross-case comparison")
            ax.grid(True, linestyle=":", alpha=0.5)
            fig.tight_layout()
            fig.savefig(png_out, dpi=200)
            plt.close(fig)
```

Notes:

- `ctx` for run steps is a `PostProcessingRunContext` with:
  - `run_root`: run output root directory
  - `run_id`: run identifier
  - `case_results`: tuple of per-case result dicts
- Comparison run steps operate on existing case artifacts only (for example CSV/parquet files that were already written during case execution).
- Keep plugin code resilient; if a step raises, pywandahydra logs the error and marks that step failed.

## 3. Register the Step Through Entry Points

In your plugin package `pyproject.toml`:

```toml
[project]
name = "my-hydra-plugins"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pywanda-hydra"]

[project.entry-points."pywandahydra.run_steps"]
compare_cases_pressure = "my_hydra_plugins.run_steps:CompareCasesPressureStep"
```

Install your plugin into the same environment as pywandahydra.

## 4. Make It Executable From Config

A step alone is not automatically executed unless included by a workflow.

Two ways to run it:

### Option A: Use the built-in composed workflow (recommended)

```yaml
execution:
  workflow:
    name: composed
    params:
      case_steps: []
      run_steps:
        - name: compare_cases_pressure
          params:
            property_name: Pressure
            mode: MAX
            output_basename: pressure_comparison
```

### Option B: Ship your own workflow plugin

Implement a workflow class and register it in `pywandahydra.workflows`.

Minimal example (`my_hydra_plugins/workflow.py`):

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from my_hydra_plugins.run_steps import CompareCasesPressureStep


class MyWorkflow:
  name = "my_comparison_workflow"
  description = "Custom workflow including cross-case comparison plots"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

    def __init__(self, params: BaseModel) -> None:
        self._p = params

    def case_steps(self, ctx):
      return []

    def run_steps(self, ctx):
      return [CompareCasesPressureStep()]
```

Register it in plugin `pyproject.toml`:

```toml
[project.entry-points."pywandahydra.workflows"]
my_comparison_workflow = "my_hydra_plugins.workflow:MyWorkflow"
```

Example run config using custom workflow:

```yaml
execution:
  workflow:
    name: my_comparison_workflow
    params: {}
```

## 5. Verify Plugin Discovery

After installation, run:

```powershell
python -m pywandahydra plugins
```

You should see your step under `Run steps` and your workflow under `Workflows`.

## 6. Troubleshooting

- Step not listed:
  - Ensure plugin is installed in the same Python environment used by pywandahydra.
  - Confirm entry-point group names exactly match expected names.
- Step listed but not executed:
  - Ensure the selected workflow includes your run step.
  - Check `execution.workflow.params` content and schema.
- Workflow fails to resolve:
  - Check `name` and `Params` in workflow class.
  - Validate `execution.workflow.params` matches `Params` schema.
- Step constructor errors:
  - Ensure nested `Params` model exists and accepts supplied `params` values.

## 7. Recommended Practices

- Put per-case calculations in case steps and cross-case aggregation/plots in run steps.
- Keep adapter/system interactions out of postprocessing steps unless necessary.
- Use strict parameter models (`extra="forbid"`) for predictable configs.
- Keep step names stable once used in production configs.
- Add tests in your plugin package for:
  - entry-point discovery
  - output file/content expectations
  - empty-run and missing-input handling for run steps

## 8. Cache Availability and Architecture Limits

### Can a comparison step read non-existing cached data?

Short answer: no, not directly.

- `run_steps` run after all cases are completed and only receive `PostProcessingRunContext` (`run_root`, `run_id`, `case_results`). They do not receive a live WANDA model handle.
- `case_steps` receive `CaseContext` with cache/scenario paths, but also do not receive the live WANDA model handle.
- Therefore, plugin steps can only read data that already exists in generated artifacts (cache parquet, exported tables/figures, or files your own prior steps wrote).

### How to process data that is currently non-existing

Use one of these patterns:

1. Add an earlier producer step:
- Create a case step that computes and writes the needed intermediate data per case.
- Then let your run step aggregate and compare those generated files.

2. Extend extraction in core (architecture change):
- If the required signal is not extracted at all, add it in the extraction layer so it is cached during model execution.
- After that, plugin steps can consume it from cache.

3. Add custom in-case postprocessing from existing cache:
- For metrics derivable from already extracted route/component series (for example pressure/head along route), compute them in a case step and persist as csv/parquet for run-level comparison.


