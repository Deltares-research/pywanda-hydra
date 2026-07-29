# Slice 04 - ScenarioDocument and loader dispatch

**Branch:** `refactor-v2/04-scenario-document`
**Depends on:** approved Slice 02
**Parallelism:** may develop with Slice 03; rebase after 03 merges
**Risk:** medium
**Recommended model:** balanced coding model

## Goal

Introduce the workbook-level `ScenarioDocument`, preserve all valid workbook rows, relocate plot
vocabulary into `scenarios`, and replace runtime source registration with explicit
extension-to-function dispatch.

## Owned files

- current scenario mapper/source registry files;
- new `scenarios/loader.py` and `scenarios/models/document.py`;
- axis/annotation model definitions and imports;
- current Excel source only where required to construct the document;
- callers that currently expect `list[ScenarioSpecification]`;
- scenario/document/dispatch tests;
- renderer imports only, without renderer behavior changes.

## Target contracts

```python
@dataclass(frozen=True, slots=True)
class ScenarioWarning:
    sheet: str
    message: str
    row: int | None = None
    column: str | None = None

class ScenarioDocument(BaseModel):
    analysis_metadata: AnalysisMetadata
    scenarios: tuple[ScenarioSpecification, ...]
    source_path: Path
    warnings: tuple[ScenarioWarning, ...] = ()
```

Use the repository's preferred model/dataclass style consistently. Exact serialization details
remain internal until the manifest slice.

## Tasks

1. Move `AxisSpec` and `PlotTextAnnotation` from post-processing into
   `scenarios/models/plot_axis.py`; rename `AxisSpec` to `AxisSpecification`.
2. Add `ScenarioDocument` and a typed warning value.
3. Return all valid workbook rows, including `include=false`.
4. Capture workbook analysis metadata once on the document.
5. Add `scenarios/loader.py` with an explicit mapping:

   ```python
   _LOADERS = {
       ".xls": load_excel_document,
       ".xlsx": load_excel_document,
       ".xlsm": load_excel_document,
   }
   ```

6. Delete `ScenarioSource`, registration decorators, mutable source registries, and bootstrap
   behavior.
7. Update current callers to consume `document.scenarios`; case-plan construction remains the
   selection point.
8. Update post-processing imports to read axis/annotation types from `scenarios`.
9. Add tests for unsupported extensions, document source path, one analysis-metadata value,
   row preservation, and deferred include filtering.

## Explicit intermediate state

`ScenarioSpecification.analysis_meta` may remain temporarily populated for current report code.
`ScenarioDocument.analysis_metadata` becomes authoritative; Slice 05 removes per-scenario copies
and rewires report access. Add an explicit comment that the temporary copy is removed by
Slice 05; do not let it become a second authoritative metadata source.

## Not in scope

- dissolving `ScenarioMeta` or renaming parameter/output fields (05);
- physically splitting the Excel parser (06);
- a loader Protocol or external source registration;
- table/figure rendering changes.

## Focused validation

```powershell
uv run ruff check .\src\pywandahydra\scenarios .\tests\unit_test\scenarios
uv run mypy src/pywandahydra/scenarios
uv run pytest -o addopts='' tests/unit_test/scenarios/ -q
uv run pytest -o addopts='' tests/unit_test/postprocessing/plotting/ -q
```

## Acceptance criteria

- exactly one visible extension-to-loader-function mapping exists;
- no `ScenarioSource`, `register_source`, or source bootstrap remains;
- all valid included/excluded rows are present in `ScenarioDocument`;
- current execution only creates plans for included scenarios;
- analysis metadata is authoritative at document level;
- `scenarios` imports neither post-processing nor WANDA;
- existing rendering behavior is unchanged.

## Handoff

- Slice 05 owns the model-shape migration and removes the temporary metadata copy.
- Slice 06 owns the final Excel package split and deletion of old paths.
- Slice 07 consumes `ScenarioDocument` in `RunPlan`.

## Agent dispatch prompt

> Implement Slice 04 from `.github/plans/refactor/04-scenario-document.md`. Introduce the
> document aggregate and explicit loader-function mapping while preserving the current scenario
> field shape for Slice 05. Keep excluded rows and move axis/annotation vocabulary without
> changing renderer behavior. Do not create a loader Protocol or registry. Rebase after Slice 03
> merges and rerun focused checks before handoff.