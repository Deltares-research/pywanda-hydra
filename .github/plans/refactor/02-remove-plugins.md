# Slice 02 - Remove external extension machinery

**Branch:** `refactor-v2/02-remove-plugins`
**Current commit:** `89c4ec0`
**Pull request:** [#30](https://github.com/Deltares-research/pywanda-hydra/pull/30)
**Depends on:** Slice 01
**Status:** active review; acceptance incomplete
**Risk:** medium

## Goal

Remove all installed-package extension discovery and custom extractor execution while keeping
the current built-in workflow/step behavior temporarily functional until Slice 10 replaces it.

This slice removes extension machinery; it does not implement another registry design.

## Current PR state

Implemented in PR #30:

- removed `importlib.metadata.entry_points` loading from extractors, workflows, themes, and
  scenario sources;
- removed the `plugins` CLI command;
- retained built-in workflow/step/theme/source registration temporarily;
- removed the extractor bootstrap call from the worker.

Outstanding against this plan:

- package entry-point declarations still exist in `pyproject.toml`;
- custom extractor Protocol, registry, configuration, case-plan data, worker execution, and
  custom cache persistence still exist;
- `resolve_extractor` contains a dangling `pass`;
- generated `test_results_slice02.txt` is tracked in the PR;
- binary WANDA fixture changes require review/removal if accidental.

## Owned files

- `pyproject.toml` plugin entry-point sections;
- `postprocessing/extraction/extractors.py`;
- extractor fields/calls in `config/loader.py`, `execution/case_plan.py`, and
  `execution/worker.py`;
- custom-extractor-only methods in `postprocessing/io/cache.py`;
- external-discovery/bootstrap compatibility code in workflows/themes/scenario sources only as
  required to remove external loading;
- old plugin/extractor tests and documentation;
- `cli/commands.py` plugin command removal already present.

## Remaining tasks

1. Remove every `[project.entry-points."pywandahydra.*"]` section from `pyproject.toml`.
2. Delete `postprocessing/extraction/extractors.py`.
3. Remove `ExecutionConfig.extractors`, `CasePlan.extractors`, hash payload entries, and builder
   arguments.
4. Remove `_run_custom_extractors` and its call from the worker.
5. Remove custom-result read/write/list methods from `ParquetCache` when semantic references
   prove no non-plugin caller remains.
6. Delete or rewrite tests whose only subject is external/custom extractor registration.
7. Keep built-in default/composed workflows, steps, themes, and XLS source behavior working as a
   temporary bridge. Do not create workflow unions or rename composed behavior.
8. Remove generated test output and accidental binary fixture modifications from the PR.
9. Update docs/examples that promise separately distributed plugins or custom extractors.

## Not in scope

- final scenario loader dispatch (Slice 04);
- WANDA boundary rename (Slice 03);
- workflow/step deletion (Slice 10);
- theme/package reorganization (Slice 09C);
- final CLI flattening (Slice 14).

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/postprocessing/test_entry_points.py tests/unit_test/postprocessing/test_extractors.py -q
uv run pytest -o addopts='' tests/unit_test/postprocessing/test_methodology_config.py tests/unit_test/execution/ -q
uv run pytest -o addopts='' tests/unit_test/test_cli_commands.py -q
uv run ruff check .\src\pywandahydra
uv run mypy src/pywandahydra
```

Remove deleted test paths from the first command and run their remaining package suites.

## Acceptance criteria

- no `project.entry-points."pywandahydra` declaration remains;
- no production import of `importlib.metadata.entry_points` remains for these features;
- no extractor Protocol, registry, config field, case-plan field, worker path, or custom cache
  persistence remains;
- the `plugins` command is absent;
- current built-in default run behavior still passes tests;
- no generated output or unexplained binary fixture change is in the PR;
- full merge gate passes.

## Handoff to Slices 03 and 04

- no external discovery or custom extraction remains;
- built-in registries may still exist only as temporary implementation details;
- Slice 03 owns dynamic model-access selection removal;
- Slice 04 owns source registry replacement;
- Slice 10 owns workflow/step deletion.

## Agent dispatch prompt

> Complete Slice 02 from `.github/plans/refactor/02-remove-plugins.md` on the active PR branch.
> Remove all package entry-point declarations and the complete custom extractor path while
> preserving temporary built-in workflow/step/theme/source behavior. Do not implement later
> package moves or workflow unions. Remove generated artifacts, run focused and full gates, and
> return a handoff report. Stop for any user-visible behavior decision not settled here.