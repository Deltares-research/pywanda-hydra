# Slice 10 - Fixed post-processing pipeline

**Branch:** `refactor-v2/10-postprocessing-pipeline`
**Depends on:** merged Slices 09B and 09C
**Risk:** high
**Recommended model:** strongest coding/reasoning model

## Goal

Delete workflows, step classes, and generic post-processing framework packages. Replace them
with one explicit fixed pipeline over final table/figure functions and stable named outcomes.

## Owned files

- current `postprocessing/core/`, `workflows/`, and `steps/`;
- remaining generic `postprocessing/io/` remnants;
- final `postprocessing/pipeline.py`;
- current runner/worker post-processing calls only;
- workflow/step/pipeline tests reorganized around functions/outcomes.

## Stable outcome contract

```python
@dataclass(frozen=True, slots=True)
class PostProcessingOutcome:
    routine_name: str
    status: Literal["succeeded", "skipped", "failed"]
    skip_reason: str | None = None
    error: str | None = None
    created_paths: tuple[Path, ...] = ()
```

```python
process_case_results(...) -> tuple[PostProcessingOutcome, ...]
process_run_results(...) -> tuple[PostProcessingOutcome, ...]
```

Routine names are explicit stable identifiers, never derived from Python function names.

## Fixed order

Case:

1. calculate/write case MIN/MAX table when requested;
2. create case figure PDF when route/time-series figures are requested.

Run:

1. combine/write run MIN/MAX table;
2. merge case PDFs.

No matching input is `skipped`, not failed.

## Tasks

1. Add fixed case/run entry points with the stable outcome contract.
2. Put applicability checks in the pipeline based on scenario content.
3. Preserve independent failure isolation: one output failure does not erase simulation success
   or prevent an independent routine.
4. Delete workflow classes, workflow/step Protocols, registries, bootstraps, `Params` models,
   `core/`, `workflows/`, `steps/`, and remaining generic `io/`.
5. Remove workflow names/params from case plans, current runner/worker, and any leftover config.
6. Update current execution callers to consume outcome tuples and derive current temporary
   post-processing success state.
7. Replace workflow/step tests with ordering, applicability, skip-reason, failure-capture, and
   generated-path tests.

## Not in scope

- `CaseStatusStore`, final persistence, or resume (11);
- final execution package layout (12);
- manifest/offline root API (13);
- CLI/public export cleanup (14).

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/postprocessing/ -q
uv run pytest -o addopts='' tests/unit_test/execution/test_worker_with_fake_adapter.py tests/unit_test/execution/test_runner.py -q
uv run mypy src/pywandahydra/postprocessing src/pywandahydra/execution
uv run ruff check .\src\pywandahydra\postprocessing
```

## Acceptance criteria

- post-processing contains only `pipeline.py`, `tables/`, `figures/`, and package exports;
- no workflow, step class, `Params`, registry, bootstrap, `core`, or generic `io` remains;
- all ordering is visible in one module;
- applicability comes only from scenario content;
- stable outcomes preserve failure isolation and paths;
- execution callers/tests pass without workflow names.

## Handoff

- Slice 11 persists outcome status without changing the outcome contract.
- Slice 12 calls case/run pipeline functions from the final engine.
- Slice 13 exposes offline post-processing through the same functions.

## Agent dispatch prompt

> Implement Slice 10 from `.github/plans/refactor/10-postprocessing-pipeline.md` after both
> capability branches merge. Delete the workflow/step framework rather than renaming it. Call
> final table/figure functions explicitly, return the exact stable outcome contract, and
> preserve independent failure behavior. Do not redesign status/resume or execution layout.