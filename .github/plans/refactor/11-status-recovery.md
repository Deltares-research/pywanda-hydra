# Slice 11 - Status, locks, fingerprints, and recovery decisions

**Branch:** `refactor-v2/11-status-recovery`
**Depends on:** Slices 08 and 10
**Risk:** high
**Recommended model:** strongest coding/reasoning model

## Goal

Replace `CaseJournal` with the exact persistence responsibilities selected in the architecture:
typed current status, run/case locks, case logs, separate fingerprints, and a pure three-way
recovery decision.

Do not recreate event history under another name.

## Owned files

- current `execution/journal.py`;
- new `execution/status.py`, `locking.py`, `fingerprints.py`, and `run_directory.py`;
- current runner/worker only for status/lock/resume integration;
- logging configuration only for per-case logs;
- status/resume/lock/artifact tests.

## Closed status values

Simulation:

- `pending`;
- `running`;
- `succeeded`;
- `failed`.

Post-processing:

- `pending`;
- `running`;
- `succeeded`;
- `failed`;
- `not_required`.

Excluded scenarios have no case plan/directory/status. Routine-level skipped/failed detail lives
in `PostProcessingOutcome`, not extra case status strings.

## CaseStatus minimum data

- schema version and case id;
- closed simulation/post-processing statuses;
- simulation and output fingerprints;
- start/finish timestamps and duration;
- latest error summary;
- tuple/list of serialized post-processing outcomes and generated paths.

Do not include attempt history, queued time, or event history without a real requirement.

## Fingerprints

Canonical JSON includes an explicit fingerprint schema version.

Simulation fingerprint includes:

- `.wdi` and companion `.wdx` content hashes;
- model upgrade option;
- effective WANDA/pywanda version data available after preparation;
- steady/unsteady choices;
- ordered `ModelParameterChange` values.

Output fingerprint includes:

- scenario tables, figures, and report configuration;
- run-level theme and table/figure formats.

Exclude run id, case/display name, output paths, timestamps, and log level. Raw data requirements
are compared with inventory and are not hidden in either fingerprint.

## Recovery decision

Implement a pure function returning `simulate`, `postprocess`, or `skip`:

| Facts | Action |
|---|---|
| no successful simulation status | simulate |
| simulation fingerprint changed | simulate |
| result store missing, incomplete, or corrupt | simulate |
| inventory does not satisfy current requirements | simulate |
| valid data but outputs missing/failed | postprocess |
| valid data but output fingerprint changed | postprocess |
| valid data and current successful outputs | skip |

## Tasks

1. Implement typed `CaseStatus` and `CaseStatusStore`.
2. Write a sibling temporary status file, flush/fsync it, and atomically replace
   `status.json`; store acquisition remains the caller's responsibility.
3. Raise a specific corruption error for malformed/unsupported status; never return "not run".
4. Implement `RunLock` and `CaseLock` with `filelock.FileLock(timeout=0)` and distinct
   `RunLockedError`/`CaseLockedError` containing the lock path and available owner metadata.
5. Treat native lock state as authoritative; a PID/owner record may be stale after a crash.
6. Add one normal `case.log` writer while the case lock is held. Do not add a shared
   multiprocess file handler.
7. Implement canonical fingerprints and the pure decision matrix.
8. Integrate enough into current runner/worker to delete `CaseJournal` and all event calls.
9. Treat lock contention as operational contention, not scientific simulation failure.
10. Add tests for atomic replacement, corruption, unsupported schema, lock contention,
    fingerprint inclusions/exclusions, data insufficiency, and the full matrix.

## Not in scope

- final execution file layout (12);
- run manifest (13);
- event history or retry attempts;
- shared/network filesystem support without explicit approval/testing.

## Decision gates

- Shared/network filesystem guarantees require user approval and tests; default support is local
  Windows filesystem.
- A shared ordered run log requires queue-listener design and explicit approval; default is one
  case log per locked case.

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/execution/test_status.py tests/unit_test/execution/test_locking.py tests/unit_test/execution/test_fingerprints.py tests/unit_test/execution/test_resume_policy.py -q
uv run pytest -o addopts='' tests/unit_test/execution/test_worker_failure.py -q
uv run mypy src/pywandahydra/execution
uv run ruff check .\src\pywandahydra\execution
```

## Acceptance criteria

- `CaseJournal`, `events.jsonl`, and all event writes are gone;
- status values are closed and corruption is explicit;
- status replacement and lock contention tests pass;
- a second active run fails immediately and clearly;
- case status/log have one writer under case lock;
- pure tests prove all recovery decisions and fingerprint boundaries;
- appearance/reduction-only changes never choose simulation when raw data suffices.

## Handoff

- Slice 12 uses these types/functions unchanged in the final engine.
- Slice 13 serializes status summaries and uses locks for offline processing.

## Agent dispatch prompt

> Implement Slice 11 from `.github/plans/refactor/11-status-recovery.md`. Replace the journal
> with atomic current status, fail-fast run/case locks, and one case log. Implement exact
> fingerprints and the pure three-way matrix. Do not recreate event history or rewrite the full
> execution layout. Treat corruption and contention explicitly and stop for filesystem/logging
> policy decisions beyond the approved local Windows scope.