# Case Step Data Export Guide

This guide explains how to implement a **case step** that exports custom-derived data during case post-processing, enabling later cross-case comparison and analysis.

### Related Guides

- **[custom_extractors.md](custom_extractors.md)** â€“ If you need to extract data while the model is open, use custom extractors instead. They have direct model access and are more powerful than case steps.

## Architecture Overview

The data flow during case execution:

```
Model Session (open)
    â†“
    â”œâ”€ Simulate (steady/unsteady)
    â”œâ”€ extract_all()  â†’ extracts component and route time-series
    â””â”€ cache.write()  â†’ persists to parquet files
    â†“
Model Session (closes)
    â†“
Case Steps (run with CaseContext)
    â”œâ”€ Read from cache (parquet files)
    â”œâ”€ Compute metrics / reformat data
    â””â”€ Export to CSV / JSON / custom format
    â†“
Run Steps (run with PostProcessingRunContext after ALL cases complete)
    â”œâ”€ Read per-case exports
    â”œâ”€ Aggregate across cases
    â””â”€ Generate comparison plots/tables
```

**Key point:** Case steps execute *after* model extraction is complete. They cannot access the live WANDA model, but they can read cached extracted data (components, routes, timeseries, envelopes) and export derived metrics for downstream analysis.

## When to Use a Case Step for Data Export

Use case steps when:

- You need to derive metrics or reformat extracted data (for example, compute max/min/mean along a route).
- You want per-case CSV/JSON exports that will later be aggregated by a run step.
- You need to filter or pivot data from components or route timeseries.
- You want to ensure custom exports exist for every case before comparison steps run.

## Example: Route Pressure/Head Statistics Export

This example creates a case step that:
1. Reads route timeseries from cache.
2. Computes per-route statistics (max, min, mean).
3. Exports a CSV for later cross-case comparison.

### 1. Plugin Package Structure

```text
my-hydra-plugins/
  pyproject.toml
  my_hydra_plugins/
    __init__.py
    case_steps.py
    run_steps.py
    workflow.py
```

### 2. Implement the Case Step

Create `my_hydra_plugins/case_steps.py`:

```python
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict

from pywandahydra.postprocessing.context import CaseContext

logger = logging.getLogger(__name__)


class ExportRouteStatisticsStep:
    """Extract per-route min/max/mean statistics from cached route data."""

    name = "export_route_statistics"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        # Optional: filter routes by name pattern (None = all routes)
        route_filter: str | None = None
        # Optional: filter properties to export
        properties: list[str] | None = None

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def applicable(self, ctx: CaseContext) -> bool:
        """Run only if routes are defined."""
        pp = ctx.scenario.post_processing
        if pp.enabled_steps and self.name not in pp.enabled_steps:
            return False
        return len(pp.routes) > 0

    def run(self, ctx: CaseContext) -> None:
        """Compute and export route statistics."""
        export_dir = ctx.case_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        rows: list[dict] = []

        # List all cached routes
        route_titles = ctx.cache.list_routes()
        for title in route_titles:
            # Optional: filter by route name
            if self._p.route_filter and self._p.route_filter not in title:
                continue

            route_data = ctx.cache.read_route(title)
            ts_df = route_data.get("timeseries")
            if ts_df is None or ts_df.empty:
                logger.debug("Route '%s' has no timeseries data â€“ skipping.", title)
                continue

            # Extract statistics from multi-index columns
            # Columns are (component, property, s_location)
            for col in ts_df.columns:
                component, prop, s_location = col
                
                # Optional: filter properties
                if self._p.properties and prop not in self._p.properties:
                    continue

                series = ts_df[col].dropna()
                if series.empty:
                    continue

                rows.append({
                    "route": title,
                    "component": component,
                    "property": prop,
                    "s_location": s_location,
                    "min": float(series.min()),
                    "max": float(series.max()),
                    "mean": float(series.mean()),
                    "std": float(series.std()),
                })

        if rows:
            stats_df = pd.DataFrame(rows)
            output_csv = export_dir / "route_statistics.csv"
            stats_df.to_csv(output_csv, index=False)
            logger.info(
                "Exported route statistics for case '%s' to %s",
                ctx.case_dir.name,
                output_csv,
            )
        else:
            logger.warning(
                "No route statistics computed for case '%s'.",
                ctx.case_dir.name,
            )
```

### 3. Create a Companion Run Step for Aggregation

Create `my_hydra_plugins/run_steps.py` to aggregate per-case exports:

```python
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from pydantic import BaseModel, ConfigDict

from pywandahydra.postprocessing.context import PostProcessingRunContext


class AggregateRouteStatisticsStep:
    """Aggregate per-case route statistics and plot cross-case comparison."""

    name = "aggregate_route_statistics"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        property_filter: str | None = None
        metric: str = "max"  # "min", "max", or "mean"

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def run(self, ctx: PostProcessingRunContext) -> None:
        """Read per-case statistics and create cross-case comparison."""
        scenarios_dir = ctx.run_root / "scenarios"
        comparisons_dir = ctx.run_root / "comparisons"
        comparisons_dir.mkdir(parents=True, exist_ok=True)

        all_stats: list[dict] = []

        for case_result in ctx.case_results:
            if case_result.get("success") is not True:
                continue

            case_id = str(case_result["case_id"])
            stats_csv = scenarios_dir / case_id / "exports" / "route_statistics.csv"

            if not stats_csv.exists():
                continue

            df = pd.read_csv(stats_csv)
            df["case_id"] = case_id
            all_stats.append(df)

        if not all_stats:
            return

        combined = pd.concat(all_stats, ignore_index=True)
        output_csv = comparisons_dir / f"route_statistics_{ctx.run_id}.csv"
        combined.to_csv(output_csv, index=False)

        # Plot: max pressure per route across cases
        if self._p.property_filter:
            filt = combined["property"] == self._p.property_filter
            plot_df = combined[filt]
        else:
            plot_df = combined

        if not plot_df.empty:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            metric_col = self._p.metric
            for case_id in plot_df["case_id"].unique():
                case_data = plot_df[plot_df["case_id"] == case_id]
                route_groups = case_data.groupby("route")[metric_col].mean()
                ax.plot(range(len(route_groups)), route_groups.values, 
                        marker="o", label=str(case_id))

            ax.set_xlabel("Route Index")
            ax.set_ylabel(f"{self._p.metric.upper()}")
            ax.set_title(f"Cross-case {self._p.metric} by route")
            ax.legend()
            ax.grid(True, linestyle=":", alpha=0.5)
            fig.tight_layout()

            plot_file = comparisons_dir / f"route_comparison_{ctx.run_id}.png"
            fig.savefig(plot_file, dpi=200)
            plt.close(fig)
```

### 4. Register Steps in Entry Points

In `pyproject.toml`:

```toml
[project]
name = "my-hydra-plugins"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pywanda-hydra"]

[project.entry-points."pywandahydra.case_steps"]
export_route_statistics = "my_hydra_plugins.case_steps:ExportRouteStatisticsStep"

[project.entry-points."pywandahydra.run_steps"]
aggregate_route_statistics = "my_hydra_plugins.run_steps:AggregateRouteStatisticsStep"
```

### 5. Use in Configuration

Example `run_config.yaml`:

```yaml
execution:
  workflow:
    name: composed
    params:
      case_steps:
        - name: export_route_statistics
          params:
            route_filter: null  # Process all routes
            properties: ["Pressure", "Head"]  # Focus on these properties
      run_steps:
        - name: aggregate_route_statistics
          params:
            property_filter: "Pressure"
            metric: "max"
```

## Cache Access Patterns

### Reading Cached Data in Case Steps

The `CaseContext.cache` provides these methods:

```python
# Read component outputs (time-series)
components_df = ctx.cache.read_components()
# -> DataFrame with MultiIndex columns: (component, property, s_location)

# List cached route titles
routes = ctx.cache.list_routes()  # -> list[str]

# Read a specific route's data
route_data = ctx.cache.read_route("Route 1")
# -> {"timeseries": df, "envelope": df, "profile": df}

# Check if cache exists
has_cache = ctx.cache.exists()  # -> bool
```

### File Layout

After case extraction, the cache directory structure is:

```
case_dir/data/
    components.parquet
    routes/
        Route_1/
            timeseries.parquet
            envelope.parquet
            profile.parquet
        Route_2/
            ...
```

## Best Practices

1. **Robustness:** Always check if cache data exists before reading.
   ```python
   if not ctx.cache.exists():
       logger.warning("No cache data for case â€“ skipping.")
       return
   ```

2. **Export to well-known formats:** Use CSV for tabular data (human-readable, cross-platform) or JSON for structured data.

3. **Named directories:** Create clear export subdirectories so run steps know where to find per-case data.
   ```python
   export_dir = ctx.case_dir / "exports"
   export_dir.mkdir(parents=True, exist_ok=True)
   ```

4. **Handle empty scenarios:** Not all cases may produce route data; gracefully skip cases with missing exports.

5. **Log progress:** Help users understand what was exported per case.
   ```python
   logger.info("Exported %d routes for case '%s'.", len(rows), ctx.case_dir.name)
   ```

6. **Chain steps:** Case steps â†’ per-case exports â†’ run steps â†’ aggregation/comparison.

## Differences from Run Steps

| Aspect | Case Step | Run Step |
|--------|-----------|----------|
| Timing | After extraction, per case | After all cases complete |
| Context | `CaseContext` | `PostProcessingRunContext` |
| Cache access | Can read extracted data | Must read from exported files |
| Can access model? | No | No |
| Use case | Compute per-case metrics, reformat | Aggregate, cross-case comparison |

## Troubleshooting

- **"Cache does not exist":** Ensure the scenario includes output/route specifications so extraction runs.
- **"Column not found":** Route timeseries use MultiIndex columns; iterate `df.columns` carefully.
- **"No data exported":** Check `logger.info()` output to confirm whether routes were found and processed.
- **Missing per-case exports in run step:** Verify the case step ran (check case journal) and export directory name matches what the run step expects.

## Extending Extracted Data

### Current Extraction Architecture

The extraction layer runs in [src/pywandahydra/postprocessing/extract.py](../../../src/pywandahydra/postprocessing/extract.py):

```
worker.py
  â”œâ”€ adapter.run_steady() / adapter.run_unsteady()
  â””â”€ extract_all(model, scenario, adapter)
      â”œâ”€ extract_component_outputs()  â†’ reads specified component time-series
      â””â”€ extract_route_outputs()       â†’ reads route plots (timeseries, envelope, profile)
  â”œâ”€ cache.write(extracted)            â†’ persists to parquet
  â””â”€ case steps now have access to cached data
```

**Key constraint:** Extraction happens while the WANDA model session is open. Plugin case steps cannot hook into this phase because they receive `CaseContext` *after* the model is closed.

### Option 1: Extend Extraction in Core

If you control the pywanda-hydra codebase, you can add custom extraction logic:

1. Add a new extraction function in [src/pywandahydra/postprocessing/extract.py](../../../src/pywandahydra/postprocessing/extract.py):

```python
def extract_custom_properties(
    model: pywanda.WandaModel,
    adapter: WandaAdapter,
) -> dict[str, pd.DataFrame]:
    """Extract custom computed properties (example: energy loss, velocity ratios)."""
    # Access the live model to compute/read additional properties
    # Return as dict of {key: DataFrame}
    pass
```

2. Call it from `extract_all()`:

```python
def extract_all(
    model: pywanda.WandaModel,
    scenario: ScenarioSpecification,
    adapter: WandaAdapter,
) -> dict[str, Any]:
    return {
        "components": extract_component_outputs(...),
        "routes": extract_route_outputs(...),
        "custom_metrics": extract_custom_properties(model, adapter),  # NEW
    }
```

3. Persist to cache by extending [src/pywandahydra/postprocessing/cache.py](../../../src/pywandahydra/postprocessing/cache.py):

```python
def write(self, extracted: dict[str, Any]) -> dict[str, str]:
    # ... existing code for components and routes ...
    
    # NEW: Write custom metrics
    custom = extracted.get("custom_metrics", {})
    if custom:
        for key, df in custom.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                path = self.data_dir / f"{key}.parquet"
                df.to_parquet(path, engine="pyarrow")
                artefacts[key] = str(path.relative_to(self.data_dir.parent))
```

4. Add a read method to access it in case steps:

```python
def read_custom(self, key: str) -> pd.DataFrame:
    """Read a custom extracted dataset."""
    path = self.data_dir / f"{key}.parquet"
    if path.exists():
        return pd.read_parquet(path, engine="pyarrow")
    return pd.DataFrame()
```

Then in your case step:

```python
def run(self, ctx: CaseContext) -> None:
    custom_df = ctx.cache.read_custom("my_custom_metrics")
    # Process and export...
```

### Option 2: Compute Derived Metrics from Existing Cache (Plugin-Only)

If you cannot modify core extraction, derive metrics from the already-extracted data in a case step:

```python
def run(self, ctx: CaseContext) -> None:
    # Read existing components or routes
    components = ctx.cache.read_components()
    
    # Example: compute energy loss per component
    # (sum of all time-series for a "Loss" property)
    loss_data = []
    for col in components.columns:
        component, prop, s_location = col
        if prop == "Energy Loss":
            total_loss = components[col].sum()
            loss_data.append({"component": component, "total_loss": total_loss})
    
    if loss_data:
        loss_df = pd.DataFrame(loss_data)
        export_dir = ctx.case_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        loss_df.to_csv(export_dir / "energy_losses.csv", index=False)
```

### Option 3: Access External Data Sources

Plugin case steps can also read from external sources (useful if computed data exists elsewhere):

```python
def run(self, ctx: CaseContext) -> None:
    case_id = ctx.case_dir.name
    
    # Example: read pre-computed results from a sibling directory
    external_data_dir = ctx.case_dir.parent.parent / "external_results"
    external_csv = external_data_dir / f"{case_id}_computed.csv"
    
    if external_csv.exists():
        df = pd.read_csv(external_csv)
        export_dir = ctx.case_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        # Re-export locally or process further
        df.to_csv(export_dir / "reexported.csv", index=False)
    else:
        logger.warning("External data not found for case %s", case_id)
```

### Option 4: Use a Preprocessor Adapter

For plugin developers who need model-level data before extraction, you can create a custom adapter that logs additional properties during model access:

1. Subclass the configured adapter and override methods to capture extra data:

```python
# my_hydra_plugins/custom_adapter.py
from pywandahydra.wanda.pywanda_adapter import PywandaAdapter

class LoggingAdapter(PywandaAdapter):
    def __init__(self):
        super().__init__()
        self.extra_data = {}
    
    def get_series(self, model, item_name, property_name):
        """Override to log additional metadata."""
        result = super().get_series(model, item_name, property_name)
        # Store extra computations or metadata
        self.extra_data[(item_name, property_name)] = {
            "mean": float(np.asarray(result).mean()),
            "std": float(np.asarray(result).std()),
        }
        return result
```

2. Use it in config by setting `adapter_class` to your custom adapter path.

3. Then a case step could read that adapter's logged data (if persisted).

**Note:** This pattern is advanced and requires careful design to avoid data leaks across cases.

### Summary: Which Approach to Use?

| Situation | Approach |
|-----------|----------|
| You control core codebase and can modify extract.py | **Option 1:** Extend extraction and cache |
| Plugin only, data derivable from components/routes | **Option 2:** Compute in case step |
| Data exists in external files/databases | **Option 3:** Read from external source |
| You need to capture data during model execution | **Option 1 or Option 4** (complex) |


