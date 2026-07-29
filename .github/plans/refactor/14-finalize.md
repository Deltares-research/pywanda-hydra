# Slice 14 - CLI, public API, imports, docs, and final tree

**Branch:** `refactor-v2/14-finalize`
**Depends on:** Slice 13
**Risk:** medium
**Recommended model:** balanced coding model; strongest if import failures span packages

## Goal

Finish the clean break without changing scientific behavior: flatten the CLI, expose supported
Python APIs, remove every transitional path, update documentation/examples, and prove the final
tree/import boundaries.

## Owned files

- root `cli.py`, `__init__.py`, and `__main__.py`;
- deletion of old `cli/` package;
- all package `__init__.py` files and final import cleanup;
- docs, README, examples, sample config, changelog, contributing/CI path updates;
- import-boundary and CLI/API tests;
- empty `optimization/` source directories.

## Final CLI

- `run` -> `prepare_run` + `execute_run`;
- `validate` -> `validate_run`;
- `status` -> `read_run_status`;
- `postprocess` -> `postprocess_run`.

Delete `plot` and `plugins` commands. Figure formats are handled by configured output settings
and the shared figure implementation.

## Public API

Root package re-exports the five application functions and only the small set of typed
result/report values required to consume them. Internal modules remain importable but are not
documented stable APIs.

## Tasks

1. Create root `cli.py` with thin Typer wrappers and consistent exception/status presentation.
2. Update `__main__.py` and project script entry point; delete `cli/`.
3. Curate root/package `__all__` and remove temporary re-exports/facades.
4. Delete every obsolete import path, compatibility bridge, empty package, and empty
   optimization placeholder.
5. Update README, `docs-user`, examples, sample YAML, changelog, and CONTRIBUTING to final
   structure, API, recovery, and extension instructions.
6. Ensure examples call public root APIs and do not reproduce orchestration.
7. Add import-boundary tests in fresh subprocesses:
   - scenarios imports no post-processing/WANDA;
   - results imports no execution/WANDA/post-processing;
   - post-processing imports no execution/WANDA;
   - status/offline root API imports no pywanda;
   - CLI help imports neither pywanda nor Matplotlib.
8. Search and remove all live references to old symbols/paths/config keys.
9. Run final release and real-WANDA gates.

## Decision gate

Whether CLI `validate` exposes strict Excel mode must be explicitly recorded in
`decision-log.md`. Do not add the flag merely because the Python parser supports it.

## Old-concept search list

At minimum search for:

```text
ScenarioMeta
ParameterChange
ChangeMode
global_overrides
reuse_existing_data
base_model_name
enabled_steps
workflow_name
workflow_params
ConfigDrivenWorkflow
ComposedWorkflow
CaseJournal
events.jsonl
ParquetCache
adapter_class
register_
bootstrap
entry_points
post_process.json
run_metadata.json
postprocessing.core
postprocessing.io
postprocessing.steps
postprocessing.workflows
postprocessing.plotting
```

Matches in changelog/history may be legitimate; production/docs/examples must describe only the
final system.

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/test_cli_commands.py tests/unit_test/test_run_api.py tests/unit_test/test_import_boundaries.py -q
uv run python -m pywandahydra --help
uv run python -c "import pywandahydra; print(pywandahydra.__all__)"
```

Final gate:

```powershell
uv run ruff check .\src\pywandahydra
uv run mypy src/pywandahydra
uv run pytest tests/unit_test/ tests/integration_test/
uv build
git diff --check
```

## Acceptance criteria

- source tree matches `architecture-target.md` except justified private helpers;
- CLI has exactly four thin commands and no business logic;
- five supported Python functions are documented/exported;
- no transitional or obsolete concept remains live;
- empty optimization directory is gone;
- docs/examples/sample config execute against final APIs;
- import boundaries and lazy WANDA/Matplotlib behavior pass in fresh processes;
- full quality/build and required real-WANDA gates pass or have explicit user disposition.

## Agent dispatch prompt

> Implement Slice 14 from `.github/plans/refactor/14-finalize.md` only after all functional
> slices merge. Flatten CLI, curate final APIs, remove every transitional path, and update all
> docs/examples. Do not alter scientific behavior to make final tests pass; return behavioral
> failures to their owning slice. Include old-symbol searches, import-boundary evidence, full
> gate output, and real-WANDA passes/skips.