# Slice 03 - WANDA model-access boundary

**Branch:** `refactor-v2/03-wanda-model-access`
**Depends on:** approved Slice 02
**Parallelism:** may develop with Slice 04; merge 03 first
**Risk:** high
**Recommended model:** strongest coding/reasoning model

## Goal

Replace the user-selectable adapter concept with one controlled, reference-safe WANDA boundary:
a complete static `WandaModelAccess` Protocol and one internal `PywandaModelAccess`
implementation.

This is a rename and cleanup of the current boundary, not another implementation layer or plugin
mechanism.

## Owned files

- all production files under `src/pywandahydra/wanda/`;
- adapter construction/type references in current execution plan/worker/runner files;
- WANDA tests and adapter test helpers;
- worker tests only where construction changes;
- root `disuse.py` when moving WANDA-specific parsing.

## Required Protocol inventory

Verify each operation with semantic references and include every operation still used by
simulation or target extraction:

- open/close a model session;
- apply one model parameter change;
- save model input;
- run steady and unsteady simulations;
- read simulation time and time steps;
- resolve output items and route pipes;
- identify a pipe item;
- read ordinary series and scalar values;
- read pipe series, length, extrema, and profile data.

Model-file copying is deliberately outside the live-model Protocol.

## Tasks

1. Create `wanda/model_access.py` with a complete non-`runtime_checkable` Protocol.
2. Rename `PywandaAdapter` and its module to internal `PywandaModelAccess` in
   `pywanda_model_access.py`.
3. Remove `adapter_class` import paths and dynamic `import_module` loading from config, runner,
   case plans, and worker. Production constructs the internal implementation directly.
4. Move case-model file operations to `model_files.py`.
5. Split generic `api.py` into:
   - `item_lookup.py`;
   - `route_tracing.py`;
   - `parameter_application.py`.
6. Keep model lifetime in `session.py` and isolated WANDA-backed checks in `validation.py`.
7. Move legacy Disuse interpretation into parameter application. Scenario models retain the
   authored raw value until this boundary validates/applies it.
8. Ensure no component/property/table/route/native pywanda wrapper leaves `wanda` or survives
   its immediate operation. Return copied strings, scalars, tuples, immutable references, and
   NumPy arrays.
9. Replace broad hand-built fakes with `create_autospec(WandaModelAccess, instance=True)` and
   one shared helper wiring the mocked session context manager.
10. Keep one importable test-only implementation only for a future spawn test; do not expose it
    from production.
11. Add or preserve tests for exact/fuzzy lookup, bulk selectors, route order/direction, unit
    conversion, Disuse, parameter errors, session close, and wrapper lifetime.

## Not in scope

- live extraction relocation (09A);
- scenario shape changes (05);
- alternative production implementations;
- configuration or Python API for choosing model access;
- changing fuzzy lookup semantics without a user decision.

## Decision gate

The existing fuzzy fallback can match multiple items. If implementation requires retaining,
narrowing, or making it explicit, stop and ask the user with concrete model/test matches. Record
the answer in `decision-log.md` before continuing.

## Focused validation

```powershell
uv run ruff check .\src\pywandahydra\wanda .\tests\unit_test\wanda
uv run mypy src/pywandahydra/wanda
uv run pytest -o addopts='' tests/unit_test/wanda/ tests/unit_test/execution/test_worker_with_fake_adapter.py tests/unit_test/execution/test_worker_failure.py -q
```

Real-WANDA gate:

```powershell
uv run pytest -o addopts='' tests/integration_test/test_disuse.py tests/integration_test/test_failed_route.py -q
```

## Acceptance criteria

- `WandaAdapter`, `PywandaAdapter`, `adapter_class`, and dynamic adapter loading are gone;
- `CasePlan` remains pickleable and contains no implementation selector;
- the static Protocol covers every target caller;
- production has exactly one concrete model-access implementation;
- model copying is outside the Protocol;
- no native wrapper escapes in any tested value;
- imports do not open a model session;
- unit/type/lint and available real-WANDA gates pass.

## Handoff

- Slice 05 imports `ModelParameterChange` into the new boundary.
- Slice 09A uses only the completed `WandaModelAccess` contract.
- Slice 12 constructs `PywandaModelAccess` inside simulation workers.

## Agent dispatch prompt

> Implement Slice 03 from `.github/plans/refactor/03-wanda-model-access.md`. Treat this as a
> static/test contract plus one internal production implementation, never a user-selectable
> adapter. Enforce stable outward values and preserve WANDA behavior. Stop for a decision on
> fuzzy matching or any native-lifetime behavior not settled by tests. Run focused validation
> after the first edit and return the required handoff report.