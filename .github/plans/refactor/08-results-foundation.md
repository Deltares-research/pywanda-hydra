# Slice 08 - Results foundation

**Branch:** `refactor-v2/08-results`
**Depends on:** Slice 07
**Risk:** high
**Recommended model:** strongest coding/reasoning model

## Goal

Create the neutral, WANDA-free durable simulation-data contract before migrating extraction or
post-processing call sites.

## Owned files

- new `src/pywandahydra/results/` except `manifest.py`;
- new `tests/unit_test/results/`;
- no current worker, cache, extraction, or post-processing implementation files.

## Required contracts

Define typed, immutable outer structures for:

- `ExtractedSimulationData`;
- component time-series data;
- route time-series, envelope, and profile data;
- `DataRequirements`;
- `ResultInventory`;
- stable component/property/location and route/property identities.

Pandas DataFrames may remain mutable payloads but must be copied/owned predictably.

## Tasks

1. Define simulation-data and route-data shapes using only stable Python/Pandas values.
2. Define explicit raw-data requirements and inventory subset/sufficiency logic.
3. Ensure identities never use plot titles or filenames.
4. Implement `ParquetResultStore` round trips preserving indexes, MultiIndex columns, units,
   locations, and route products.
5. Under a future case lock, store writes follow this completion protocol:
   - remove prior completion marker before changing data;
   - close all Parquet writers;
   - write inventory/fingerprint metadata through sibling temporary files;
   - atomically replace metadata;
   - atomically replace a small completion marker last.
6. Readers trust only a valid marker whose listed files and hashes exist.
7. Missing, corrupt, or partial stores report incomplete and never satisfy resume.
8. Keep the package free of execution, WANDA, pywanda, Matplotlib, and post-processing imports.
9. Do not migrate `ParquetCache` callers yet; Slice 09A does that atomically.

## Tests

Add focused tests for:

- empty/component/route round trips;
- MultiIndex and numeric location fidelity;
- deterministic inventory serialization;
- subset and missing-requirement reports;
- stable identity independent of title;
- missing/corrupt files and marker;
- interrupted write leaving an incomplete store;
- forbidden imports.

## Focused validation

```powershell
uv run ruff check .\src\pywandahydra\results .\tests\unit_test\results
uv run mypy src/pywandahydra/results
uv run pytest -o addopts='' tests/unit_test/results/ -q
uv run python -c "import pywandahydra.results; import sys; assert 'pywanda' not in sys.modules"
```

## Acceptance criteria

- typed data/store/inventory round trips preserve scientific data;
- requirements identify insufficiency precisely;
- partial/corrupt stores cannot appear complete;
- no display name is a data key;
- no forbidden package import exists;
- no production caller migration is included.

## Handoff

- Slice 09A uses these contracts unchanged for live extraction/store migration.
- Slice 11 uses inventory sufficiency for recovery decisions.
- Slice 13 adds `manifest.py` beside this package.

## Agent dispatch prompt

> Implement Slice 08 from `.github/plans/refactor/08-results-foundation.md` as a tested,
> WANDA-free foundation only. Do not migrate current cache/extraction callers. Define stable
> identities, explicit requirements, inventory, and transactional completion so later slices do
> not redesign persistence. Enforce forbidden imports in tests and stop for any persisted-format
> decision not settled by this plan.