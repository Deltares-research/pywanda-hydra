# Refactor v2 implementation tracker

**Updated:** 2026-08-04
**Target:** the package structure in [`architecture-target.md`](architecture-target.md)
**Execution rules:** [`README.md`](README.md)
**Validation gates:** [`validation.md`](validation.md)
**Decision record:** [`decision-log.md`](decision-log.md)

This directory is the implementation source of truth for the new pywanda-hydra structure.
Older A-J plans are superseded. Do not implement workflow discriminated unions,
`ComposedWorkflow`, `postprocessing/runtime/`, or another plugin/registration layer.

## Current baseline

- Repository default branch: `master` at `8b34cf7` when the v2 work began.
- Integration branch: `refactor`, containing merged Slices 01 through 06.
- Slices 07 and 08 are merged into `refactor`.
- Slices 09A, 09B, and 09C are merged into `refactor`.

## Status

| Slice | Plan | Branch | Depends on | Risk | Status |
|---|---|---|---|---|---|
| 01 | [`01-cleanup.md`](01-cleanup.md) | `refactor-v2/01-cleanup` | baseline | low | merged into `refactor` |
| 02 | [`02-remove-plugins.md`](02-remove-plugins.md) | `refactor-v2/02-remove-plugins` | 01 | medium | merged into `refactor` |
| 03 | [`03-wanda-model-access.md`](03-wanda-model-access.md) | `refactor-v2/03-wanda-model-access` | 02 | high | merged into `refactor` |
| 04 | [`04-scenario-document.md`](04-scenario-document.md) | `refactor-v2/04-scenario-document` | 02 | medium | merged into `refactor` |
| 05 | [`05-scenario-models.md`](05-scenario-models.md) | `refactor-v2/05-scenario-models` | 03, 04 | high | merged into `refactor` |
| 06 | [`06-excel-loader.md`](06-excel-loader.md) | `refactor-v2/06-excel-loader` | 05 | medium | merged into `refactor` |
| 07 | [`07-config-run-api.md`](07-config-run-api.md) | `refactor-v2/07-config-run-api` | 03, 04, 05, 06 | high | merged into `refactor` |
| 08 | [`08-results-foundation.md`](08-results-foundation.md) | `refactor-v2/08-results` | 07 | high | merged into `refactor` |
| 09A | [`09a-result-extraction.md`](09a-result-extraction.md) | `refactor-v2/09a-extraction` | 03, 05, 08 | high | merged into `refactor` |
| 09B | [`09b-tables.md`](09b-tables.md) | `refactor-v2/09b-tables` | 09A | medium | merged into `refactor` |
| 09C | [`09c-figures.md`](09c-figures.md) | `refactor-v2/09c-figures` | 09A | high | merged into `refactor` |
| 10 | [`10-postprocessing-pipeline.md`](10-postprocessing-pipeline.md) | `refactor-v2/10-postprocessing-pipeline` | 09B, 09C | high | pending |
| 11 | [`11-status-recovery.md`](11-status-recovery.md) | `refactor-v2/11-status-recovery` | 08, 10 | high | pending |
| 12 | [`12-execution-engine.md`](12-execution-engine.md) | `refactor-v2/12-execution` | 03, 09A, 10, 11 | very high | pending |
| 13 | [`13-manifest-run-api.md`](13-manifest-run-api.md) | `refactor-v2/13-manifest-run-api` | 07, 08, 12 | high | pending |
| 14 | [`14-finalize.md`](14-finalize.md) | `refactor-v2/14-finalize` | 13 | medium | pending |

Status vocabulary:

- **pending:** no implementation branch should start until dependencies merge;
- **active:** one coding agent owns the slice;
- **decision required:** implementation is paused for explicit user choice;
- **in review:** focused checks pass and a PR awaits approval;
- **implemented:** reviewed implementation exists on its slice branch;
- **merged:** included in the integration/default branch and safe as a new baseline.

## Dependency graph

```text
01 -> 02 -> 03 ---------+
          \-> 04 -> 05 -> 06 -> 07 -> 08 -> 09A -> 09B --+
                 ^       ^                 |       09C --+-> 10 -> 11 -> 12 -> 13 -> 14
                 +-- 03 -+                 +-- 03,05
                                                    08 ---------> 11
```

Readable ordering:

1. Finish and approve Slice 02.
2. Develop Slices 03 and 04 from the approved Slice 02 base; merge 03 first, then rebase and merge 04.
3. Run Slices 05 through 09A sequentially.
4. Develop 09B and 09C in separate worktrees with disjoint ownership; merge 09B, rebase 09C, then merge 09C.
5. Run Slices 10 through 14 sequentially.

## Active Slice 02 gate

PR #30 now satisfies the approved Slice 02 scope:

- package metadata and production code contain no external entry-point discovery;
- the custom extractor contract, configuration, execution path, persistence, tests, and example
  are removed;
- built-in workflow/step/theme/source registration remains only as the planned temporary bridge;
- generated test output is removed;
- the WANDA fixture is restored to the `master` blob, and the upgrade test uses a temporary copy;
- all 370 tests pass, including 39 real-WANDA/preflight/integration tests;
- Ruff, mypy, coverage, package build, and `git diff --check` pass.

The remaining gate is explicit user approval and merge. Do not start dependent Slices 03 or 04
until PR #30 is merged and recorded as their base.

## Coordinator checkpoints

At every slice boundary the coordinator must:

1. start from the latest approved/merged prerequisite;
2. choose a model based on cost versus reasoning depth;
3. enforce the slice's owned files and exclusions;
4. stop for a user decision when the plan does not settle behavior or a public contract;
5. review the handoff report and run the merge gate;
6. ask the user before merging or dispatching a dependent slice;
7. update this table immediately after approval and merge.

## Final target checks

The refactor is complete only when:

- root `run.py` provides the five supported Python use cases;
- root `cli.py` is a thin four-command Typer interface;
- scenario loading returns `ScenarioDocument` through explicit function dispatch;
- `WandaModelAccess` is static and `PywandaModelAccess` is the sole internal implementation;
- durable simulation data lives in `results` and live extraction in `execution`;
- post-processing contains only `pipeline.py`, `tables/`, and `figures/`;
- `CaseJournal`/`events.jsonl` are replaced by atomic status, locks, and case logs;
- resume selects simulate, post-process, or skip from separate validity facts;
- one versioned `run_manifest.json` drives provenance and offline post-processing;
- no plugin registry, workflow/step layer, generic post-processing bucket, dynamic model-access
  selection, schema facade, or empty optimization package remains;
- lint, type checking, tests, coverage, package build, import boundaries, spawn behavior, and
  required real-WANDA checks pass.