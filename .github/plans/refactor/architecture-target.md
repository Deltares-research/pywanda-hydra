# Approved target architecture

This file records the package target implemented by Slices 03-14. It is intentionally
self-contained because local review documents under `.claude/` are not tracked.

## Package tree

```text
src/pywandahydra/
|-- __init__.py
|-- __main__.py
|-- cli.py                         # thin Typer wrappers
|-- run.py                         # supported application use cases
|-- logging_config.py
|-- VERSION
|-- py.typed
|
|-- config/
|   |-- __init__.py
|   |-- models.py                  # user-authored YAML only
|   `-- loader.py                  # parse, validate, resolve paths
|
|-- scenarios/
|   |-- __init__.py
|   |-- loader.py                  # explicit extension-to-function dispatch
|   |-- models/
|   |   |-- __init__.py
|   |   |-- document.py
|   |   |-- scenario.py
|   |   |-- parameter_change.py
|   |   |-- post_processing.py
|   |   |-- table_minmax.py
|   |   |-- plot_axis.py
|   |   |-- plot_route.py
|   |   |-- plot_time_series.py
|   |   `-- validators.py
|   `-- excel/
|       |-- __init__.py
|       |-- loader.py
|       |-- cases.py
|       |-- post_processing.py
|       `-- validation.py
|
|-- wanda/
|   |-- __init__.py
|   |-- model_access.py            # static WandaModelAccess Protocol
|   |-- pywanda_model_access.py    # sole production implementation
|   |-- model_files.py
|   |-- session.py
|   |-- item_lookup.py
|   |-- route_tracing.py
|   |-- parameter_application.py
|   `-- validation.py
|
|-- execution/
|   |-- __init__.py
|   |-- plans.py
|   |-- outcomes.py
|   |-- run_cases.py
|   |-- case_execution.py
|   |-- result_extraction.py
|   |-- fingerprints.py
|   |-- status.py
|   |-- locking.py
|   `-- run_directory.py
|
|-- results/
|   |-- __init__.py
|   |-- simulation_data.py
|   |-- data_requirements.py
|   |-- parquet_store.py
|   `-- manifest.py
|
`-- postprocessing/
    |-- __init__.py
    |-- pipeline.py
    |-- tables/
    |   |-- __init__.py
    |   |-- case_minmax.py
    |   |-- run_minmax.py
    |   `-- export.py
    `-- figures/
        |-- __init__.py
        |-- axes.py
        |-- route.py
        |-- time_series.py
        |-- pdf_pages.py
        |-- case_pdf.py
        |-- run_pdf.py
        |-- layout.py
        |-- theme.py
        |-- export.py
        `-- assets/
            |-- __init__.py
            `-- Deltares_logo.png
```

There is no `optimization`, plugin, workflow, step, `core`, `runtime`, generic
post-processing `io`, source registry, schema facade, or journal module in the target.

## Supported Python API

Root `run.py` owns the five first-class application use cases:

```python
prepare_run(config_path: Path, *, workers: int | None = None, resume: bool | None = None) -> RunPlan
execute_run(plan: RunPlan) -> RunResult
validate_run(config_path: Path, *, preflight: bool = False) -> ValidationReport
read_run_status(run_dir: Path) -> RunStatus
postprocess_run(run_dir: Path, *, case_ids: set[str] | None = None) -> RunResult
```

The CLI exposes `run`, `validate`, `status`, and `postprocess` by calling these functions. It
contains presentation and Typer exception translation only.

## Configuration shape

```yaml
run_id: example_run
output_root: ./runs
description: Example run
scenario_file: ./scenarios/cases.xls

model:
  path: ./model/base_model.wdi
  wanda_bin: C:/Program Files (x86)/Deltares/Wanda 4.8/Bin64
  upgrade: false

simulation:
  steady: true
  unsteady: true

execution:
  workers: 4
  resume: true

outputs:
  theme: deltares_light
  figure_formats: [pdf]
  table_formats: [csv]
```

Removed keys/concepts include `base_model_name`, `reuse_existing_data`, `verbose`, workflows,
extractors, global overrides, and per-scenario theme/step selection. Log level is an invocation
option, not scientific configuration.

## Scenario aggregate

```text
ScenarioDocument
|-- analysis_metadata
|-- scenarios
|   `-- ScenarioSpecification
|       |-- number
|       |-- include
|       |-- name
|       |-- parameter_changes
|       |-- post_processing
|       |   |-- tables.minmax
|       |   |-- figures.routes
|       |   |-- figures.time_series
|       |   `-- report.(description, appendix, chapter, date)
|       |-- extra_columns
|       `-- source
|-- source_path
`-- warnings
```

The loader preserves all valid rows, including `include=false`. Case-plan construction filters
selection. Workbook-level analysis metadata is stored once. Lenient optional parsing emits
typed warnings; it never silently omits malformed content.

## WANDA boundary

- `WandaModelAccess` is a complete, non-runtime-checkable Protocol for static typing and
  autospec tests.
- `PywandaModelAccess` is the sole internal production implementation.
- There is no config/import-path implementation selection.
- Model-file copying is outside the live-model Protocol.
- Component, property, table, route-component, and other native pywanda wrappers never leave
  `wanda` or survive their immediate operation.
- Outward values are strings, scalars, immutable references, tuples, and copied NumPy arrays.
- A case selected for simulation always starts from a fresh base-model copy. Skip and
  post-process actions never copy/open a WANDA model.

## Results and post-processing

- Live extraction runs inside the open model session in `execution/result_extraction.py`.
- `ExtractedSimulationData`, `DataRequirements`, `ResultInventory`, and
  `ParquetResultStore` live in WANDA-free `results`.
- Storage identities do not use display titles or filenames.
- Store completion is explicit; partial/corrupt stores are never resumable.
- `postprocessing/pipeline.py` calls plain table/figure functions in fixed visible order.
- There are no workflow or step classes.
- Every routine returns a stable named succeeded/skipped/failed outcome.

## Status, locking, and recovery

Per run:

```text
<run>/
|-- .run.lock
|-- run_manifest.json
|-- inputs/
|-- scenarios/
|-- tables/
`-- figures/
```

Per case:

```text
scenarios/<case_id>/
|-- .case.lock
|-- status.json
|-- case.log
|-- model/
|-- data/
|-- tables/
`-- figures/
```

There is no `events.jsonl`. `CaseStatusStore` writes current typed status atomically and reports
corruption. `RunLock` rejects a second active invocation. `CaseLock` remains defensive.

Resume uses three separate facts:

1. simulation fingerprint for inputs that alter WANDA results;
2. stored result inventory compared with current raw-data requirements;
3. output fingerprint for reductions, report text, layout, theme, and formats.

Decision matrix:

| Facts | Action |
|---|---|
| no successful simulation, changed simulation fingerprint, missing/corrupt store, or missing raw data | simulate |
| valid data plus failed/missing outputs or changed output fingerprint | post-process |
| valid data plus current successful outputs | skip |

## Dependency direction

```text
cli -> run -> config, scenarios, execution, results, postprocessing
execution -> config, scenarios, wanda, results, postprocessing
wanda -> config, scenarios
results -> config, scenarios
postprocessing -> config, scenarios, results
```

Forbidden dependencies:

- `config` imports no application package;
- `scenarios` imports neither WANDA nor post-processing;
- `wanda` imports no execution, results persistence, or post-processing;
- `results` imports no execution, WANDA, or post-processing;
- post-processing imports no execution, WANDA, or pywanda;
- CLI imports root application functions, not deep implementation modules.

Importing package/config/scenarios/results/status/offline APIs must not initialize pywanda or
Matplotlib.