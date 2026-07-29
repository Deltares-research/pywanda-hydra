# Shared validation gates

All commands run from the repository root in Windows PowerShell.

## Baseline and merge gate

```powershell
uv run ruff check .\src\pywandahydra
uv run mypy src/pywandahydra
uv run pytest tests/unit_test/ tests/integration_test/
uv build
git diff --check
git status --short
```

Record pass, fail, and skip counts. Integration tests skip when WANDA cannot be located. A skip
is an environment limitation, not a passing real-WANDA gate.

## Focused tests

The repository pytest configuration applies whole-package coverage. Disable it for narrow
feedback loops:

```powershell
uv run pytest -o addopts='' <test-paths> -q
```

Every slice runs its listed focused check immediately after the first substantive edit and
again before handoff.

## Required pre-handoff checks

```powershell
uv run ruff check <touched-source-paths> <touched-test-paths>
uv run mypy <touched-source-paths>
uv run pytest -o addopts='' <focused-test-paths> -q
```

Then the coordinator runs the full merge gate.

## Real-WANDA checkpoints

Run on a designated Windows machine with WANDA and the local pywanda wheel:

- Slice 03: session, lookup, parameter application, route tracing, native lifetime;
- Slice 09A: live extraction and result inventory;
- Slice 12: sequential and spawn case execution;
- Slice 13: resume and offline post-processing end to end;
- Slice 14: full release integration suite.

Agents without WANDA still add/update integration tests and report them as not executed.

## Import checks

Run import-boundary checks in fresh subprocesses so prior imports cannot hide a violation:

```powershell
uv run python -c "import pywandahydra.scenarios; import sys; assert not any(k.startswith(('pywandahydra.postprocessing','pywandahydra.wanda','pywanda')) for k in sys.modules)"
uv run python -c "import pywandahydra.results; import sys; assert not any(k.startswith(('pywandahydra.execution','pywandahydra.postprocessing','pywandahydra.wanda','pywanda')) for k in sys.modules)"
uv run python -c "from pywandahydra.run import read_run_status, postprocess_run; import sys; assert 'pywanda' not in sys.modules"
uv run python -m pywandahydra --help
```

## Spawn checks

Any slice changing worker imports, plan/outcome types, bootstrapping, or execution dispatch must
run:

- plan/outcome pickle round-trip unit tests;
- a spawned-process unit test using an importable test-only model-access implementation;
- real multi-case WANDA spawn integration where available.

Mocks are not sent across spawn boundaries.

## Visual checks

Figure capability changes require:

- deterministic figure/PDF unit tests;
- a known input rendered before and after;
- image pixel/content checks or an approved visual comparison;
- no blank pages, clipped text, overlap, or changed route/time-series semantics.

## File and branch hygiene

Before handoff:

```powershell
git diff --check
git status --short
git diff --name-status <slice-base>...HEAD
```

Reject:

- generated test-output files;
- changed binary model fixtures unless required and reviewed;
- htmlcov, caches, temporary models, logs, or copied run outputs;
- unrelated formatting or dependency lock churn;
- changes outside slice ownership.

## Coverage and build

The merge gate uses the repository's configured coverage threshold. The final refactor target
also follows the contribution guideline of meaningful coverage above 80% where practical.
`uv build` must produce a wheel that imports from an installed environment, not only the source
tree.

## Handoff evidence

The agent report includes:

- exact commands;
- pass/fail/skip counts;
- WANDA availability;
- old-symbol/import searches;
- generated artifact check;
- known unverified behavior;
- follow-up contract for dependent slices.