# Slice 07 - Run configuration and preparation API

**Branch:** `refactor-v2/07-config-run-api`
**Depends on:** Slices 03 and 06
**Risk:** high
**Recommended model:** strongest coding/reasoning model

## Goal

Separate user-authored configuration from prepared run data and establish the stable root
application seam before replacing execution internals.

## Authored YAML model

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

## Owned files

- all `config/` production files;
- new root `run.py`;
- new `execution/plans.py` and temporary current-engine bridge call sites;
- current CLI run/validate wrappers only;
- config/run API tests, config examples, and focused docs.

## Prepared contracts

```python
@dataclass(frozen=True, slots=True)
class RunPlan:
    configuration: RunConfiguration
    config_path: Path
    model_path: Path
    wanda_bin: Path
    run_dir: Path
    scenario_document: ScenarioDocument
    cases: tuple[CasePlan, ...]
```

`CasePlan` remains frozen and pickleable and contains no implementation selector or native
object. Exact final outcome types arrive in Slice 12.

## Tasks

1. Define `RunConfiguration`, `ModelConfiguration`, `SimulationConfiguration`,
   `ExecutionConfiguration`, and `OutputConfiguration`.
2. Remove old authored keys: `base_model_name`, `reuse_existing_data`, workflow, extractor,
   verbose, and any leftover global override.
3. Parse YAML/JSON with helpful collected errors.
4. Resolve paths relative to the config file into new prepared values; never mutate the parsed
   configuration model.
5. Move derived runtime context out of `config`; remove `RunContext`/`RunMetadata` as config
   types.
6. Add root `prepare_run()` and `validate_run()` with no Typer dependency.
7. `prepare_run` loads `ScenarioDocument`, validates safe/unique included case names, applies
   API overrides immutably, performs isolated WANDA preflight, and returns `RunPlan` without
   copying case models.
8. `validate_run(preflight=False)` stays WANDA-free; `preflight=True` performs isolated WANDA
   checks.
9. Add temporary `execute_run(plan)` that unpacks the plan and directly calls the current
   execution runner. Keep the root name/argument stable; Slice 12 replaces internals/results.
10. Move CLI and config-driven example setup to the root functions.
11. Update YAML examples/docs as a clean break.

## Not in scope

- final run manifest (13);
- three-way recovery (11/12);
- final CLI flattening/public exports (14);
- result requirements/inventory (08/09A).

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/test_config_loader.py tests/unit_test/test_cli_commands.py tests/unit_test/test_run_api.py -q
uv run pytest -o addopts='' tests/unit_test/execution/test_runner.py -q
uv run ruff check .\src\pywandahydra\config .\src\pywandahydra\run.py .\src\pywandahydra\execution\plans.py
uv run mypy src/pywandahydra/config src/pywandahydra/run.py src/pywandahydra/execution/plans.py
```

## Acceptance criteria

- `config` contains authored models/parsing only;
- path resolution is non-mutating;
- `prepare_run` creates no case model or output files;
- CLI/example no longer duplicate setup orchestration;
- new YAML has exactly the approved four sections and no removed keys;
- temporary `execute_run` behavior matches the existing engine.

## Handoff

- Slice 08 may use final output/scenario vocabulary for requirements.
- Slice 12 replaces only the private execution bridge, not root API names.
- Slice 13 completes all five root functions and manifest behavior.

## Agent dispatch prompt

> Implement Slice 07 from `.github/plans/refactor/07-config-run-api.md`. Keep configuration
> purely authored and root `run.py` as the composition boundary. Establish stable
> `prepare_run`, `validate_run`, and temporary `execute_run` signatures without implementing
> the final manifest/recovery engine. Update CLI/example call sites and run focused/full gates.