# Slice 09B - Table output capability

**Branch/worktree:** `refactor-v2/09b-tables`
**Depends on:** merged Slice 09A
**Parallelism:** may run with 09C under strict ownership
**Risk:** medium
**Recommended model:** balanced coding model

## Goal

Create the final `postprocessing/tables/` capability with pure MIN/MAX calculation separated
from table persistence. Current step wrappers remain thin temporary callers until Slice 10.

## Exclusive ownership

- current `postprocessing/reports/tables.py`;
- already-created `postprocessing/tables/export.py`;
- new `postprocessing/tables/case_minmax.py` and `run_minmax.py`;
- current `steps/summary_table.py` and `steps/aggregate_tables.py` only as temporary callers;
- table/report/summary/aggregate tests moved under `tests/unit_test/postprocessing/tables/`.

Do not edit:

- figures, plotting, PDF, theme, layout, or assets;
- `postprocessing/pipeline.py`, workflow/core packages, worker/runner;
- config/scenario/results contracts;
- `postprocessing/__init__.py` or shared test conftest files.

## Required functions

```python
calculate_case_minmax_table(...) -> pd.DataFrame
write_case_minmax_table(...) -> tuple[Path, ...]
combine_case_minmax_tables(...) -> pd.DataFrame
write_run_minmax_table(...) -> tuple[Path, ...]
```

Use `MinMaxTableSpecification` and `ParquetResultStore` from prior slices.

## Tasks

1. Move per-case MIN/MAX calculation into a pure function with no I/O.
2. Persist a calculated table separately through `tables/export.py`.
3. Combine per-case tables deterministically at run level.
4. Separate run persistence from combination.
5. Handle empty/missing case inputs as explicit no-data results, not exceptions caused by
   directory iteration.
6. Make current table step wrappers delegate only; leave no scientific logic in them.
7. Delete `reports/tables.py` and the empty `reports/` package.
8. Add tests for MultiIndex/flat columns, MIN/MAX, missing properties, empty data, deterministic
   case order, formats, and calculation without filesystem effects.

## Decision gate

Changing `summary_table.csv` or aggregated output filenames is user-visible. Stop and ask the
user before renaming files; record the answer in `decision-log.md`.

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/postprocessing/tables/ tests/unit_test/postprocessing/steps/ -k "table or summary or aggregate" -q
uv run ruff check .\src\pywandahydra\postprocessing\tables
uv run mypy src/pywandahydra/postprocessing/tables
```

## Acceptance criteria

- calculation has no I/O;
- persistence has no Matplotlib/PDF dependency;
- run combination is deterministic;
- no generic reports table module remains;
- temporary step wrappers are logic-free delegates;
- no file outside exclusive ownership changed.

## Parallel merge rule

Merge 09B first. Slice 09C rebases afterward. Any conflict in table/figure source or package
exports is a scope violation returned to the originating branch, not an integration task.

## Agent dispatch prompt

> Implement Slice 09B from `.github/plans/refactor/09b-tables.md` in the table-only worktree.
> Respect exclusive ownership. Build pure calculation and separate persistence, leaving old
> table step classes as thin temporary callers for Slice 10. Do not edit figures, pipeline,
> package exports, worker, config, scenarios, or shared fixtures. Stop before user-visible
> filename changes.