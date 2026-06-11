# Custom Extractors Developer Guide

This guide explains how to implement **custom extractors** to pull additional data from live WANDA models during case execution, enabling advanced post-processing and cross-case comparisons.

## Overview

**Extractors** are plugins that run while the WANDA model is open, allowing direct model access. They extract custom data beyond the standard component outputs and route plots, which is then cached and available to case/run steps.

### Why Use Extractors?

- Extract computed properties (e.g., energy loss, efficiency metrics)
- Read model-specific data not in standard scenarios
- Trigger model callbacks or post-model operations
- Prepare data for cross-case comparison

### Data Flow

```
Model Open
├─ extract_all()          → components, routes
├─ extractors[0].extract() → {"my_metric": df}
├─ extractors[1].extract() → {"energy_data": df}
└─ Model Close
    ↓
cache.write_custom()
├─ case_dir/data/custom/my_metric.parquet
└─ case_dir/data/custom/energy_data.parquet
    ↓
case_steps: ctx.cache.read_custom("my_metric")
```

## Implementation

### 1. Create Extractor Class

Implement the `Extractor` protocol in your plugin package:

```python
# my_extractors/extractors.py
from __future__ import annotations

import logging

import pandas as pd
from pydantic import BaseModel, ConfigDict

from pywandahydra.postprocessing.extractors import ExtractionContext

logger = logging.getLogger(__name__)


class CustomMetricsExtractor:
    """Extract computed metrics from open model."""

    name = "custom_metrics"
    description = "Compute energy loss and efficiency metrics"

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        include_efficiency: bool = True
        energy_threshold: float = 100.0

    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()

    def extract(self, ctx: ExtractionContext) -> dict[str, pd.DataFrame]:
        """Extract custom metrics from the model.

        Args:
            ctx: ExtractionContext with access to:
                - ctx.model: open pywanda.WandaModel
                - ctx.adapter: WandaAdapter for model operations
                - ctx.scenario: ScenarioSpecification
                - ctx.case_id: case identifier
                - ctx.case_dir: case output directory
                - ctx.cache: optional pre-extracted cache

        Returns:
            Dict mapping metric name → DataFrame. Can be:
            - {"metric": df}  → persists as metric.parquet
            - {"route_data": {"ts": df, "envelope": df}}  → nested structure
        """
        try:
            # Access extracted components (if available from prior extraction)
            if ctx.cache:
                components = ctx.cache.read_components()
                logger.info("Using pre-extracted components for case '%s'", ctx.case_id)
            else:
                # Fallback: use adapter directly
                logger.debug("Cache not yet available, extracting fresh")
                components = pd.DataFrame()

            # Compute metrics
            metrics = []

            # Example 1: Sum energy loss across all components
            if "Energy Loss" in [col[1] for col in components.columns]:
                energy_total = 0.0
                for col in components.columns:
                    if col[1] == "Energy Loss":
                        energy_total += float(components[col].sum())
                
                if energy_total > self._p.energy_threshold:
                    metrics.append({
                        "property": "Energy Loss",
                        "total": energy_total,
                        "exceeds_threshold": True,
                    })

            # Example 2: Compute efficiency if requested
            if self._p.include_efficiency and not components.empty:
                try:
                    # Access model directly via adapter
                    time_steps = ctx.adapter.get_time_steps(ctx.model)
                    flow_vals = self._get_property(ctx, "Flow", components)
                    pressure_vals = self._get_property(ctx, "Pressure", components)

                    if flow_vals and pressure_vals:
                        efficiency = sum(pressure_vals) / (sum(flow_vals) + 0.001)
                        metrics.append({
                            "property": "Efficiency",
                            "value": efficiency,
                        })
                except Exception as e:
                    logger.warning("Failed to compute efficiency: %s", e)

            result_df = pd.DataFrame(metrics) if metrics else pd.DataFrame()
            return {"custom_metrics": result_df}

        except Exception as e:
            logger.error("Extractor '%s' failed: %s", self.name, e, exc_info=True)
            return {}

    @staticmethod
    def _get_property(ctx: ExtractionContext, prop: str, components: pd.DataFrame) -> list[float]:
        """Helper: extract property values from components."""
        vals = []
        for col in components.columns:
            if col[1] == prop:
                vals.extend(components[col].dropna().tolist())
        return vals
```

### 2. Register via Entry Points

In your plugin's `pyproject.toml`:

```toml
[project]
name = "my-hydra-extractors"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pywanda-hydra"]

[project.entry-points."pywandahydra.extractors"]
custom_metrics = "my_extractors.extractors:CustomMetricsExtractor"
```

### 3. Configure Extractors in YAML

Create a run config with the `execution.extractors` section:

```yaml
run_id: test_extractors
output_root: ./runs
description: Run with custom extractors

model:
  model_path: ./model.wdi
  run_steady: true
  run_unsteady: true
  readonly: true

scenario_file: ./scenarios.xlsx

execution:
  mode: sequential
  n_workers: 1
  resume: false
  
  # Custom extractors to run during model execution
  extractors:
    - name: custom_metrics
      params:
        include_efficiency: true
        energy_threshold: 100.0
  
  # Post-processing (runs after extraction + caching)
  methodology:
    name: default
    params: {}
```

### 4. Access in Case Steps

Once cached, case steps can read custom extractor outputs:

```python
# In a case step
from pydantic import BaseModel, ConfigDict

class MyAnalysisStep:
    name = "my_analysis"
    
    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
    
    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()
    
    def applicable(self, ctx) -> bool:
        return True
    
    def run(self, ctx) -> None:
        # Read custom extracted data
        custom_df = ctx.cache.read_custom("custom_metrics")
        
        if custom_df.empty:
            logger.info("No custom metrics for case %s", ctx.case_dir.name)
            return
        
        # Process and export
        output_path = ctx.case_dir / "exports" / "analysis.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        custom_df.to_csv(output_path, index=False)
        logger.info("Exported analysis to %s", output_path)
```

### 5. Access in Run Steps

After all cases, run steps can aggregate custom extracted data:

```python
from pywandahydra.postprocessing.context import RunStepContext

class AggregateMetricsStep:
    name = "aggregate_metrics"
    
    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
    
    def __init__(self, params: Params | None = None) -> None:
        self._p = params or self.Params()
    
    def run(self, ctx: RunStepContext) -> None:
        scenarios_dir = ctx.run_root / "scenarios"
        all_metrics = []
        
        for case_result in ctx.case_results:
            if case_result.get("success") is not True:
                continue
            
            case_id = str(case_result["case_id"])
            case_dir = scenarios_dir / case_id
            cache = ParquetCache(case_dir)
            
            # Read custom extracted data
            metrics_df = cache.read_custom("custom_metrics")
            if not metrics_df.empty:
                metrics_df["case_id"] = case_id
                all_metrics.append(metrics_df)
        
        if all_metrics:
            combined = pd.concat(all_metrics, ignore_index=True)
            output_csv = ctx.run_root / "aggregated_metrics.csv"
            combined.to_csv(output_csv, index=False)
            logger.info("Aggregated metrics: %s", output_csv)
```

## ExtractionContext Reference

When your extractor's `extract()` method is called, it receives an `ExtractionContext` with:

| Field | Type | Description |
|-------|------|-------------|
| `model` | `pywanda.WandaModel` | Open model handle (live session) |
| `adapter` | `WandaAdapter` | Adapter for model operations (resolve items, get series, etc.) |
| `scenario` | `ScenarioSpecification` | Scenario definition |
| `case_id` | `str` | Case identifier |
| `case_dir` | `Path` | Case output directory (for logging, metadata) |
| `cache` | `ParquetCache \| None` | Pre-extracted cache (available after first extractor) |

## Return Value Format

Extractors return a `dict[str, Any]` where each value is either:

### Simple DataFrame
```python
return {
    "my_metrics": df  # → persists as case_dir/data/custom/my_metrics.parquet
}
```

### Nested Structure (like routes)
```python
return {
    "route_custom": {
        "timeseries": df,  # → case_dir/data/custom/route_custom/timeseries.parquet
        "profile": df,     # → case_dir/data/custom/route_custom/profile.parquet
    }
}
```

Empty dict `{}` signals no data extracted (not an error).

## Best Practices

### 1. Handle Exceptions Gracefully
```python
try:
    # extraction logic
    result = {... }
except Exception as e:
    logger.error("Extractor failed: %s", e, exc_info=True)
    return {}  # Return empty dict on failure
```

### 2. Check Cache Availability
```python
def extract(self, ctx: ExtractionContext) -> dict[str, pd.DataFrame]:
    if ctx.cache is None:
        # First extractor; cache is empty
        # You must compute data from model or return {}
        logger.debug("No prior cache available")
    else:
        # Subsequent extractors; can read prior extractions
        prior_data = ctx.cache.read_components()
```

### 3. Log Progress
```python
logger.info("Extractor '%s' starting for case '%s'", self.name, ctx.case_id)
logger.debug("Extracted %d rows for case '%s'", len(result_df), ctx.case_id)
```

### 4. Validate Parameters
```python
class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")  # Strict schema
    threshold: float = Field(gt=0, description="Must be positive")
```

### 5. Test with Mock Context
```python
# In unit tests
from pywandahydra.postprocessing.context import ExtractionContext

mock_ctx = ExtractionContext(
    model=mock_model,
    adapter=mock_adapter,
    scenario=test_scenario,
    case_id="test_case",
    case_dir=tmp_path,
)
result = extractor.extract(mock_ctx)
assert not result.get("my_data").empty
```

## Ordering & Dependencies

Extractors run **sequentially** in the order listed in `execution.extractors` config:

```yaml
execution:
  extractors:
    - name: extractor_a  # Runs first
    - name: extractor_b  # Runs second (can read from extractor_a if needed)
    - name: extractor_c  # Runs last
```

Each extractor's `ExtractionContext.cache` is updated before the next extractor runs, so downstream extractors can read prior results.

## Troubleshooting

### "Unknown extractor: my_extractor"
- Ensure plugin is installed in the same Python environment as pywandahydra
- Check entry point spelling in `pyproject.toml`
- Run `python -m pywandahydra plugins` to verify discovery

### "Extractor failed" but no error details
- Check case journal at `case_dir/state.json` and `case_dir/events.jsonl`
- Look for log output during run (check `--log-level DEBUG`)
- Add try/except in your extract() method for better error messages

### "Cache not yet available" for first extractor
- First extractor always has `ctx.cache is None`
- Either use the model/adapter directly, or ensure extraction runs as a prior step

### Nested output not persisted as expected
- Ensure nested dict contains only DataFrames (not other types)
- Check `case_dir/data/custom/` directory structure after run
- Use `cache.read_custom()` to verify what was persisted

## Complete Example Plugin

Full plugin package structure:

```text
my-hydra-extractors/
  pyproject.toml
  my_extractors/
    __init__.py
    extractors.py
  tests/
    test_extractors.py
```

**pyproject.toml:**
```toml
[project]
name = "my-hydra-extractors"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pywanda-hydra"]

[project.entry-points."pywandahydra.extractors"]
energy_loss = "my_extractors.extractors:EnergyLossExtractor"
```

**tests/test_extractors.py:**
```python
import pytest
from my_extractors.extractors import EnergyLossExtractor
from pywandahydra.postprocessing.context import ExtractionContext

def test_energy_loss_extractor(tmp_path):
    extractor = EnergyLossExtractor()
    mock_ctx = ExtractionContext(...)
    result = extractor.extract(mock_ctx)
    assert "energy_loss" in result
    assert not result["energy_loss"].empty
```

## Next Steps

- Check [case_step_data_export.md](case_step_data_export.md) to see how case steps read custom extracted data
- See [external_processing_step_setup.md](external_processing_step_setup.md) for cross-case run-step examples
- Run `python -m pywandahydra plugins` to list all available extractors
