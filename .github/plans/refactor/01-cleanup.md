# Slice 01 - Cleanup and fresh-model invariant

**Branch:** `refactor-v2/01-cleanup`
**Commit:** `7ba3206`
**Status:** implemented; prerequisite in the current Slice 02 stack
**Risk:** low

## Purpose

Remove verified dead plotting code and establish the invariant that a case selected for actual
simulation starts from a fresh copy of the base WANDA model.

## Implemented scope

- removed the dead route-plot object hierarchy and its tests;
- removed unused scenario parameter iteration helper;
- removed duplicate concrete pywanda adapter methods;
- removed the copied-model reuse shortcut;
- updated relevant WANDA tests.

## Contract handed to later slices

- Resume may skip before case-model preparation.
- Once case-model preparation is called, stale WANDA artifacts are removed and source model
  files are copied fresh.
- Slice 03 may rename/restructure the WANDA boundary without preserving duplicate method names.
- Slice 04 may relocate the surviving axis/annotation types after dead plot models are gone.

## Verification required before integration

```powershell
uv run pytest -o addopts='' tests/unit_test/wanda/test_create_scenario.py tests/unit_test/wanda/test_pywanda_adapter.py -q
uv run pytest -o addopts='' tests/unit_test/postprocessing/plotting/ -q
uv run ruff check .\src\pywandahydra
uv run mypy src/pywandahydra
```

## Branch hygiene note

The stacked diff currently shows a changed binary WANDA fixture. Before Slice 01/02 reaches the
default branch, verify whether the binary difference is an intentional fixture update or a test
side effect. A model-running test must not mutate a tracked source fixture in place.

## Acceptance record

Mark this slice merged only after:

- its stacked/base PR relationship is resolved;
- generated or accidental binary changes are removed;
- the full merge gate passes on the integration branch.