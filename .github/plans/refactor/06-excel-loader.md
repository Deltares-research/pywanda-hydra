# Slice 06 - Excel package and visible validation warnings

**Branch:** `refactor-v2/06-excel-loader`
**Depends on:** Slice 05
**Risk:** medium
**Recommended model:** balanced coding model

## Goal

Finish the scenario package by splitting Excel loading by workbook responsibility and ensuring
lenient parsing never silently omits malformed optional content.

## Owned files

- current Excel source and mapper remnants;
- new `scenarios/excel/` package;
- `scenarios/loader.py` integration;
- old `scenarios/schema.py`, `mapper.py`, and `sources/` deletion;
- scenario loading/validation tests and user documentation.

## Target ownership

| Module | Responsibility |
|---|---|
| `excel/loader.py` | open workbook, coordinate sheets, build `ScenarioDocument` |
| `excel/cases.py` | Cases sheet, identity, parameters, analysis metadata, extra columns |
| `excel/post_processing.py` | Output/Rplots/Tplots parsing |
| `excel/validation.py` | structural errors and typed warnings |

Avoid generic `helpers.py` or parser class hierarchies.

## Tasks

1. Move workbook orchestration, cases, post-processing sheets, and validation into the target
   modules.
2. Keep required workbook structure as an error in every mode.
3. In lenient mode, optional malformed/missing content may be skipped only with a typed warning
   containing sheet, row/column where available, message, and expected shape.
4. Add `strict=True` to promote every parser warning/optional-content omission into one
   collected `ScenarioValidationError`; use the same parser functions.
5. Preserve all valid rows and workbook analysis metadata from prior slices.
6. Delete old mapper/source/schema-facade paths and update all imports to curated scenario
   exports.
7. Add tests for multiple simultaneous issues, strict promotion, lenient warnings, malformed
   rows, missing optional sheets, aliases, NaN handling, and unchanged happy-path workbook data.
8. Update workbook format documentation.

## Decision gate

The Python strict argument is required. Whether `validate` exposes a CLI strict flag is deferred
to Slice 14 and requires user approval if not already recorded.

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/scenarios/test_xls_source.py tests/unit_test/scenarios/test_xls_preflight.py tests/unit_test/scenarios/test_scenario.py -q
uv run ruff check .\src\pywandahydra\scenarios
uv run mypy src/pywandahydra/scenarios
uv run python -c "import pywandahydra.scenarios"
```

## Acceptance criteria

- old `mapper.py`, `sources/`, and `schema.py` no longer exist;
- no registry, bootstrap, decorator, or reverse package import remains;
- strict and lenient use one parser;
- every lenient omission is represented in `ScenarioDocument.warnings`;
- all existing workbook behavior is covered and passes.

## Handoff

- Slice 07 calls only `load_scenario_document` and consumes typed validation output.
- Slice 13 persists the document in the run manifest.

## Agent dispatch prompt

> Implement Slice 06 from `.github/plans/refactor/06-excel-loader.md`. Split by workbook
> responsibility, not generic helpers. Lenient means warn and continue, never silently ignore;
> strict promotes all warnings using the same parser. Delete obsolete facades and update imports
> in this slice. Do not change scenario model shape or add another source abstraction.