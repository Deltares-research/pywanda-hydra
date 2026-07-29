# Slice 05 - Scenario model reshape

**Branch:** `refactor-v2/05-scenario-models`
**Depends on:** Slices 03 and 04
**Risk:** high
**Recommended model:** strongest coding/reasoning model

## Goal

Implement the approved scenario aggregate as one vertical schema migration and remove unused or
misleading parameter/config concepts without compatibility aliases.

## Target shape

```text
ScenarioSpecification
|-- number
|-- include
|-- name
|-- parameter_changes
|-- post_processing
|   |-- tables.minmax
|   |-- figures.routes
|   |-- figures.time_series
|   `-- report.(description, appendix, chapter, date)
|-- extra_columns
`-- source
```

Recommended focused types:

- `ModelParameterChange`;
- `MinMaxTableSpecification`;
- `AxisSpecification`;
- `RoutePlotSpecification`;
- `TimeSeriesPlotSpecification`;
- `TablePostProcessingConfiguration`;
- `FigurePostProcessingConfiguration`;
- `ReportConfiguration`;
- `PostProcessingConfiguration`.

## Owned files

- all files under `scenarios/models/`;
- current Excel model construction;
- scenario-field consumers in execution, WANDA validation/application, and post-processing;
- `config/models.py` only for global override removal;
- affected tests and examples.

## Tasks

1. Dissolve `ScenarioMeta`; flatten number/include/name.
2. Move report fields into `post_processing.report`.
3. Add exact `tables`, `figures`, and `report` subgroups.
4. Rename `ParameterChange` to `ModelParameterChange`; remove `ChangeMode` and `mode`.
5. Keep authored parameter values raw. WANDA-specific Disuse interpretation stays at the WANDA
   boundary established in Slice 03.
6. Rename table/time-series models and modules descriptively with full words.
7. Remove per-scenario analysis metadata; use `ScenarioDocument.analysis_metadata`.
8. Thread analysis metadata through the current case-plan/context path as a temporary bridge
   until `RunPlan` in Slice 07 owns it.
9. Preserve unknown workbook columns in `extra_columns`.
10. Remove `global_overrides` and all application, validation, fingerprint/hash, test, YAML, and
    documentation references.
11. Remove `enabled_steps` and per-scenario theme. Use the built-in default theme temporarily;
    Slice 07 supplies run-level output settings.
12. Update all consumers and behavior tests atomically. Do not preserve old field aliases.

## Not in scope

- run YAML restructuring (07);
- physical Excel package split (06);
- physical table/figure post-processing restructure (09B/09C);
- schema facade deletion before all imports are ready (06).

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/scenarios/ tests/unit_test/test_config_loader.py -q
uv run pytest -o addopts='' tests/unit_test/wanda/test_api.py tests/unit_test/wanda/test_validation.py -q
uv run pytest -o addopts='' tests/unit_test/postprocessing/steps/ tests/unit_test/postprocessing/reports/ -q
uv run mypy src/pywandahydra/scenarios src/pywandahydra/wanda src/pywandahydra/execution src/pywandahydra/postprocessing
```

## Acceptance criteria

- no production match remains for `ScenarioMeta`, `ChangeMode`, `global_overrides`,
  `enabled_steps`, or per-scenario theme;
- no scenario contains duplicated analysis metadata;
- report content renders from the new paths;
- workbook scientific requests remain equivalent;
- included/excluded rows still behave correctly;
- no old/new alias or compatibility facade is added.

## Handoff

- Slice 06 receives the final scenario constructors and can split Excel safely.
- Slice 07 receives the final authored scenario document/config vocabulary.
- Slices 09B/09C consume the final table/figure specifications.

## Agent dispatch prompt

> Implement Slice 05 from `.github/plans/refactor/05-scenario-models.md` as one vertical schema
> migration. Use the exact approved shape and update every consumer/test in the same slice.
> Do not add lifecycle wrappers, aliases, or physical post-processing moves. Report source-wide
> searches proving removed concepts are gone and stop for any user-visible naming decision not
> settled here.