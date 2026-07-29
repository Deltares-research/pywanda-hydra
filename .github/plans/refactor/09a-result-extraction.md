# Slice 09A - Live extraction and result-store migration

**Branch:** `refactor-v2/09a-extraction`
**Depends on:** Slices 03, 05, and 08
**Risk:** high
**Recommended model:** strongest coding/reasoning model

## Goal

Move all live-model extraction into execution, return typed simulation data, and migrate every
reader/writer from `ParquetCache` to `ParquetResultStore`. Prepare disjoint export modules before
the 09B/09C parallel window.

## Owned files

- current `postprocessing/extraction/extract.py` and extraction tests;
- new `execution/result_extraction.py`;
- current worker extraction/store integration only;
- `postprocessing/io/cache.py` and every cache import/call site;
- extraction/cache tests moved to execution/results ownership;
- `postprocessing/io/export.py` for a mechanical table/figure split only;
- current export imports/tests needed for that split.

## Required contracts

```python
def extract_simulation_data(
    model: ModelHandle,
    access: WandaModelAccess,
    requirements: DataRequirements,
) -> ExtractedSimulationData:
    ...
```

The model handle is opaque outside `wanda`; extraction may only pass it back to methods on
`WandaModelAccess`.

## Tasks

1. Move extraction to `execution/result_extraction.py` and use a descriptive entry point.
2. Consume only `WandaModelAccess`; remove direct pywanda imports and native wrapper handling.
3. Derive raw extraction requirements from final scenario output specifications using stable
   component/property/location and route/property identities.
4. Do not use plot titles or output filenames as store keys.
5. Return `ExtractedSimulationData` and write through `ParquetResultStore`.
6. Commit store completion/inventory only after all required data is durable.
7. Migrate every post-processing/offline reader from `ParquetCache` to the result store without
   changing table/figure behavior.
8. Delete `postprocessing/extraction/` and `postprocessing/io/cache.py`; add no cache alias.
9. Move extraction tests to `tests/unit_test/execution/test_result_extraction.py` and cache/store
   tests to `tests/unit_test/results/`.
10. Before parallel work, split shared `postprocessing/io/export.py` mechanically into
    `postprocessing/tables/export.py` and `postprocessing/figures/export.py`; update current
    callers and delete the shared module. Do not otherwise reorganize capability logic.

## Not in scope

- final table/figure module organization (09B/09C);
- workflow/step deletion (10);
- resume/fingerprints/status (11);
- execution runner/worker replacement (12).

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/execution/test_result_extraction.py tests/unit_test/results/ -q
uv run pytest -o addopts='' tests/unit_test/postprocessing/ -q
uv run mypy src/pywandahydra/execution/result_extraction.py src/pywandahydra/results src/pywandahydra/postprocessing
uv run ruff check .\src\pywandahydra\execution\result_extraction.py .\src\pywandahydra\results .\src\pywandahydra\postprocessing
```

Real-WANDA gate:

```powershell
uv run pytest -o addopts='' tests/integration_test/test_failed_route.py -q
```

## Acceptance criteria

- post-processing imports neither WANDA, pywanda, nor live extraction;
- no production `ParquetCache` reference remains;
- extraction returns typed stable values and inventory matches the store;
- route/component identity is independent of title;
- existing table/figure outputs read the new store unchanged;
- shared export has been split before 09B/09C branches start;
- all focused/full and available real-WANDA gates pass.

## Handoff

- 09B exclusively owns `postprocessing/tables/` and table step wrappers.
- 09C exclusively owns `postprocessing/figures/`, plotting/PDF/theme files, and figure wrappers.
- Neither parallel branch edits shared package exports, config/scenario models, worker/runner, or
  pipeline/workflow files.

## Agent dispatch prompt

> Implement Slice 09A from `.github/plans/refactor/09a-result-extraction.md` as one vertical
> migration from live WANDA extraction through durable result storage. Use the completed
> `WandaModelAccess` and results contracts unchanged. Migrate all cache consumers and split
> export mechanically, but do not reorganize table/figure logic or workflows. Prove forbidden
> imports and old cache names are gone; report real-WANDA execution or skips.