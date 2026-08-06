# pywandahydra user guide

`pywandahydra` runs an Excel scenario document against a WANDA model and keeps simulation data separate from derived tables, figures, and reports. A run directory contains `run_manifest.json`, copied authored inputs, case status, durable data, and generated outputs.

## Commands

The CLI has four commands:

```powershell
pywandahydra validate run.yaml
pywandahydra run run.yaml --workers 4 --resume
pywandahydra status ./runs/my_run
pywandahydra postprocess ./runs/my_run --case case_a
```

`validate` checks authored inputs without opening WANDA unless Python callers request preflight validation. `postprocess` uses committed results only.

## Configuration

```yaml
run_id: my_run
output_root: ./runs
scenario_file: ./scenarios/cases.xls
model:
  path: ./model/base_model.wdi
  wanda_bin: C:/Program Files (x86)/Deltares/Wanda 4.8/Bin64
simulation:
  steady: true
  unsteady: true
execution:
  workers: 1
  resume: false
outputs:
  figure_formats: [pdf]
  table_formats: [csv]
```

The scenario loader returns a `ScenarioDocument`. It retains valid included and excluded rows, records analysis metadata once, and supports typed warnings for optional workbook values.

## Python API

```python
from pywandahydra import (
    execute_run,
    postprocess_run,
    prepare_run,
    read_run_status,
    validate_run,
)

report = validate_run("run.yaml")
result = execute_run(prepare_run("run.yaml"))
status = read_run_status("runs/my_run")
rerendered = postprocess_run("runs/my_run")
```

These five functions are the supported application API. Model access, extraction, storage, and figure internals are implementation details.
