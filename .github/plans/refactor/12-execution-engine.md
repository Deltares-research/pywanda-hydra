# Slice 12 - Final execution engine and automatic recovery

**Branch:** `refactor-v2/12-execution`
**Depends on:** Slices 03, 09A, 10, and 11
**Risk:** very high
**Recommended model:** strongest available coding/reasoning model

## Goal

Replace old runner/worker/case-plan/artifact modules with the final explicit execution engine and
wire automatic simulate/post-process/skip behavior through already-tested contracts.

## Final module ownership

| Module | Required ownership |
|---|---|
| `plans.py` | frozen `RunPlan`/pickleable `CasePlan`; no native/live objects |
| `outcomes.py` | frozen `CaseResult`/`RunResult`; derived count properties |
| `run_cases.py` | select actions, sequential/spawn dispatch, aggregate case results |
| `case_execution.py` | `simulate_case` and WANDA-free `postprocess_case` |
| `result_extraction.py` | live-model extraction established in 09A |
| `fingerprints.py` | canonical fingerprints and pure decision functions |
| `status.py` | current status model/store only |
| `locking.py` | run/case lock context managers only |
| `run_directory.py` | directory names and input/log/status paths only |

Avoid service classes or generic coordinator/context modules.

## Outcome contracts

```python
@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    action: Literal["simulate", "postprocess", "skip"]
    success: bool
    duration_s: float | None = None
    error: str | None = None
    post_processing: tuple[PostProcessingOutcome, ...] = ()

@dataclass(frozen=True, slots=True)
class RunResult:
    run_id: str
    cases: tuple[CaseResult, ...]
    post_processing: tuple[PostProcessingOutcome, ...] = ()
```

Counts such as success/failed/skipped are derived from `cases`.

## Case sequence

```text
case lock
  -> mark simulation running
  -> copy fresh case model
  -> construct PywandaModelAccess
  -> open one session
  -> apply parameter changes
  -> run configured simulations
  -> extract required stable data
  -> close model
  -> commit result store/inventory
  -> mark simulation succeeded
  -> process case outputs from store
  -> update output status
  -> CaseResult
release lock
```

## Tasks

1. Finalize every module in the ownership table.
2. Delete old `runner.py`, `worker.py`, `case_plan.py`, `artifacts.py`, and temporary execution
   bridges after all callers migrate.
3. Parent orchestration selects action before dispatch.
4. Dispatch only `simulate` actions through sequential/spawn case execution.
5. Run post-process-only actions sequentially in the parent under each case lock for
   deterministic WANDA-free logging.
6. Skip actions do not copy files, open WANDA, or rewrite successful status/output.
7. Simulate actions always copy a fresh model.
8. Run aggregate post-processing after all case actions.
9. Keep WANDA/pywanda imports lazy inside simulation/preflight workers; status/offline paths are
   WANDA-free.
10. Add plan/outcome pickle round trips.
11. Add a spawned-process unit test using one importable test-only model-access implementation.
12. Add sequential, multi-case spawn, mixed action, failure isolation, lock, and recovery tests.
13. Run real-WANDA sequential/spawn integration where available.

## Not in scope

- final run manifest/root API completion (13);
- CLI/public export cleanup (14);
- redesigning contracts from Slices 03/08/10/11.

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/execution/ -q
uv run pytest -o addopts='' tests/unit_test/test_run_api.py -q
uv run mypy src/pywandahydra/execution src/pywandahydra/run.py
uv run ruff check .\src\pywandahydra\execution .\src\pywandahydra\run.py
```

Real-WANDA gate:

```powershell
uv run pytest -o addopts='' tests/integration_test/test_disuse.py tests/integration_test/test_failed_route.py tests/integration_test/test_multiprocess_run.py -q
```

## Acceptance criteria

- execution directory matches target modules with no old files/bridges;
- plans/outcomes cross spawn boundaries without native objects;
- simulate/post-process/skip behavior matches the pure matrix;
- skip/post-process never copy/open WANDA;
- simulation always uses a fresh copy;
- case failures remain isolated and aggregate outputs run deterministically;
- unit/spawn and required real-WANDA checks pass or have explicit user disposition.

## Handoff

- Slice 13 completes root use cases and manifest around these stable results.
- Slice 14 only changes presentation/import/docs, not execution behavior.

## Agent dispatch prompt

> Implement Slice 12 from `.github/plans/refactor/12-execution-engine.md` as the final execution
> vertical slice. Use completed model-access, results, pipeline, status, lock, and fingerprint
> contracts without redesign. Delete old modules only after all callers migrate. Add pickle and
> spawn tests and clearly report real-WANDA passes/skips. Stop if a target contract cannot
> represent observed behavior.