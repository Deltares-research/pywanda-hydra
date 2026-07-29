# Slice 13 - Run manifest and complete application API

**Branch:** `refactor-v2/13-manifest-run-api`
**Depends on:** Slices 07, 08, and 12
**Risk:** high
**Recommended model:** strongest coding/reasoning model

## Goal

Make one versioned manifest the machine-readable source for provenance and offline output, and
complete all five root application functions over the final execution engine.

## Owned files

- new `results/manifest.py`;
- root `run.py`;
- `execution/run_directory.py` only for manifest/input paths;
- old metadata/log JSON writers if any remain;
- run API, manifest, status, and offline-postprocessing tests.

## Manifest v1 minimum data

- manifest and directory schema versions;
- resolved `RunConfiguration`;
- complete `ScenarioDocument`;
- package/Python/pywanda and relevant WANDA version information;
- creation timestamp and invocation provenance;
- config/workbook/model source names and content hashes;
- run id/root and output settings.

Authored inputs are copied to `inputs/` for human provenance. They are not a second
machine-readable source of truth.

## Root API

```python
prepare_run(config_path: Path, *, workers: int | None = None, resume: bool | None = None) -> RunPlan
execute_run(plan: RunPlan) -> RunResult
validate_run(config_path: Path, *, preflight: bool = False) -> ValidationReport
read_run_status(run_dir: Path) -> RunStatus
postprocess_run(run_dir: Path, *, case_ids: set[str] | None = None) -> RunResult
```

`postprocess_run` returns `CaseResult(action="postprocess", ...)` plus run-level outcomes.

## Tasks

1. Define manifest v1 with explicit unsupported-version errors.
2. Write/read manifest atomically.
3. Copy and hash authored inputs under `inputs/`.
4. Remove `run_metadata.json`, timestamped JSON "run logs", and any
   `post_process.json` assumption.
5. Complete the five root functions over final execution/results/pipeline contracts.
6. `read_run_status` reads manifest/status only and surfaces corrupt status explicitly.
7. `postprocess_run` acquires run/case locks, validates store sufficiency, runs configured
   case/run outputs, and never imports/opens WANDA.
8. Missing/corrupt/insufficient stores produce actionable errors instructing resume/simulation;
   offline post-processing never silently simulates.
9. Delay Matplotlib import until figure rendering is requested.
10. Add manifest round-trip/version/corruption/source-hash tests and offline table/PDF recovery
    tests.

## Decision gate

Manifest v1 is a clean break. Reading/migrating older future manifest versions is not promised.
Stop and ask before adding backward migration or silently accepting an unknown schema.

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/results/test_manifest.py tests/unit_test/test_run_api.py -q
uv run pytest -o addopts='' tests/integration_test/test_offline_postprocess.py -q
uv run python -c "from pywandahydra.run import read_run_status, postprocess_run; import sys; assert 'pywanda' not in sys.modules"
uv run mypy src/pywandahydra/run.py src/pywandahydra/results
uv run ruff check .\src\pywandahydra\run.py .\src\pywandahydra\results
```

## Acceptance criteria

- one `run_manifest.json` is the sole machine-readable run source;
- no duplicate runtime metadata/config JSON remains;
- all five root functions are typed/tested and share implementation with future CLI;
- offline status/post-processing imports and runs without WANDA;
- store insufficiency/corruption is explicit;
- manifest source hashes/provenance round trip deterministically.

## Handoff

- Slice 14 exposes these functions and updates all user-facing material.
- No later slice changes manifest semantics without a user decision.

## Agent dispatch prompt

> Implement Slice 13 from `.github/plans/refactor/13-manifest-run-api.md`. Add one atomic
> versioned manifest and complete the five root use cases. Remove duplicate metadata/config
> artifacts. Prove status/offline post-processing are WANDA-free and never silently simulate.
> Do not begin CLI formatting or compatibility migration without user approval.