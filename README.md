# pywandahydra

`pywandahydra` executes WANDA scenario workbooks, stores durable simulation data, and generates configured tables and figures. Each included scenario runs from a fresh model copy and can later be resumed or post-processed offline.

## Quick start

Create a YAML configuration using the supported shape:

```yaml
run_id: my_first_run
output_root: ./runs
scenario_file: ./scenarios/cases.xls

model:
  path: ./model/base_model.wdi
  wanda_bin: C:/Program Files (x86)/Deltares/Wanda 4.8/Bin64

simulation:
  steady: true
  unsteady: true

execution:
  workers: 4
  resume: true

outputs:
  figure_formats: [pdf]
  table_formats: [csv]
```

Validate and run it:

```powershell
pywandahydra validate run.yaml
pywandahydra run run.yaml
pywandahydra status ./runs/my_first_run
pywandahydra postprocess ./runs/my_first_run
```

`postprocess` reads committed simulation data and does not open WANDA. Pass `--case <case-id>` more than once to regenerate outputs for selected cases.

## Python API

The supported application API is exported from `pywandahydra`:

```python
from pywandahydra import execute_run, prepare_run, read_run_status

plan = prepare_run("run.yaml", workers=4, resume=True)
result = execute_run(plan)
status = read_run_status(plan.run_dir)
```

The remaining supported functions are `validate_run` and `postprocess_run`. See [examples/run_from_config.py](examples/run_from_config.py) and [examples/data/run_config.yaml](examples/data/run_config.yaml).

## Development

Run the quality gate from the repository root:

```powershell
uv run ruff check .\src\pywandahydra
uv run mypy src/pywandahydra
uv run pytest tests/unit_test/ tests/integration_test/
uv build
```

WANDA-dependent integration tests require a local WANDA installation and the bundled `pywanda` wheel.
