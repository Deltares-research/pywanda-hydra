# Slice 02 - Remove external extension machinery

**Branch:** `refactor-v2/02-remove-plugins`
**Pull request:** [#30](https://github.com/Deltares-research/pywanda-hydra/pull/30)
**Depends on:** Slice 01
**Status:** in review; implementation and local merge gate complete
**Risk:** medium

## Goal

Remove all installed-package extension discovery and custom extractor execution while keeping
the current built-in workflow/step behavior temporarily functional until Slice 10 replaces it.

This slice removes extension machinery; it does not implement another registry design.

## Implemented scope

Implemented in PR #30:

- removed `importlib.metadata.entry_points` loading from extractors, workflows, themes, and
  scenario sources;
- removed every `[project.entry-points."pywandahydra.*"]` package declaration;
- removed the `plugins` CLI command;
- removed the custom extractor Protocol, registry, configuration, case-plan data, worker path,
  and custom Parquet persistence;
- removed or rewrote extractor/plugin-only tests, documentation, and examples;
- retained built-in workflow/step/theme/source registration temporarily;
- removed generated `test_results_slice02.txt`;
- restored the binary WANDA fixture to the `master` blob and isolated the upgrade test in a
  temporary model copy.

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

## Completion record

1. Source-wide searches find no package entry-point declaration or production
  `importlib.metadata.entry_points` call.
2. Source-wide searches find no extractor Protocol/registry/config/plan/worker/cache symbol.
3. Obsolete extractor configuration is rejected by a regression test.
4. Built-in default/composed workflow, step, theme, and XLS source behavior remains available.
5. User documentation states that supported capabilities ship with pywandahydra rather than
  separately installed plugins.
6. Generated and accidental binary changes are absent from the prospective diff against
  `master`.

## Not in scope

- final scenario loader dispatch (Slice 04);
- WANDA boundary rename (Slice 03);
- workflow/step deletion (Slice 10);
- theme/package reorganization (Slice 09C);
- final CLI flattening (Slice 14).

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/postprocessing/ tests/unit_test/execution/ -q
uv run pytest -o addopts='' tests/unit_test/test_cli_commands.py -q
uv run ruff check .\src\pywandahydra
uv run mypy src/pywandahydra
```

Local merge-gate result:

- 370 passed: 331 non-native unit tests with 84.97% coverage plus 39
  real-WANDA/preflight/integration tests;
- Ruff passed for all production code and changed surviving tests/examples;
- mypy passed for 75 production source files;
- source distribution and wheel build passed;
- `git diff --check` passed;
- tracked WANDA fixture hash remained identical to `master` after native tests.

## Acceptance criteria

- no `project.entry-points."pywandahydra` declaration remains;
- no production import of `importlib.metadata.entry_points` remains for these features;
- no extractor Protocol, registry, config field, case-plan field, worker path, or custom cache
  persistence remains;
- the `plugins` command is absent;
- current built-in default run behavior still passes tests;
- no generated output or unexplained binary fixture change is in the PR;
- full merge gate passes.

All acceptance criteria are satisfied locally. User approval and PR merge remain required before
this branch becomes the base for Slices 03 and 04.

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