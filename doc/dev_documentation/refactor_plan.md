# `pywanda-hydra` Refactor Plan

Sequential, reviewable steps to reach the target architecture described in
the architectural review. Each step is independently shippable: code keeps
running between steps, tests stay green, and the public surface only
hardens â€” it never breaks silently.

Conventions used in this document:

- **Goal** â€” single sentence the step achieves.
- **Why** â€” rationale linked to the review item.
- **Changes** â€” concrete file-level edits.
- **Verify** â€” what proves the step is done.
- **Risk / Rollback** â€” the failure mode and how to back out.

Numbering matches the review items (Â§3.x) where applicable so reviewers
can cross-check.

---

## Step 0 â€” Baseline & branch hygiene

**Goal.** Make sure the starting point is clean before any structural
change.

**Changes.**

- Confirm `Refactor-Structure` is up to date with `master`.
- Run the full test suite once and record current coverage (the
  `--cov-fail-under 50` floor).
- Tag the current commit: `git tag pre-refactor-baseline`.

**Verify.** `pytest` is green; tag exists.

**Risk / Rollback.** None.

---

## Step 1 â€” Path-typed configs and `RunResult` cleanup  (Â§3.8, Â§3.9)

**Goal.** Eliminate `str | Path` lies, idiomatic `field(default_factory=list)`,
and centralise the str-at-the-pywanda-boundary rule.

**Why.** Today validators on `ModelSpecification`, `RunContext`, `RunConfig`
declare `str | Path` but always coerce to `str`, forcing every consumer to
re-wrap with `Path(...)`. `pywanda.WandaModel(...)` cannot accept `Path`
objects (it expects `str`), which is the only legitimate reason to ever
materialise the path as text â€” and that reason lives at exactly one
boundary.

**Changes.**

1. In [src/pywandahydra/config/models.py](../../src/pywandahydra/config/models.py):
   - Type all paths as `Path` (`model_path`, `wanda_bin`, `root_dir`).
   - Validators become `mode="before"` and return `Path` (expand `~`,
     strip whitespace, then `Path(...)`).
   - For `wanda_bin`, keep the trailing-separator rule but apply it on a
     `Path` (use `Path` + a small helper that returns a `Path` whose
     `str()` ends with `"\\\\"` â€” store as `Path` and only stringify at
     the pywanda call-site).
2. In [src/pywandahydra/config/loader.py](../../src/pywandahydra/config/loader.py),
   `RunConfig.output_root` and `scenario_file` become `Path` with the
   same pattern.
3. In [src/pywandahydra/execution/runner.py](../../src/pywandahydra/execution/runner.py),
   replace the `RunResult.results: list[...] = None / __post_init__`
   construct with `results: list[dict[str, Any]] = field(default_factory=list)`
   and delete `__post_init__`.
4. Audit consumers (`grep` for `Path(.*\.model_path)`, etc.) and remove
   the redundant `Path(...)` wraps now that the field is already a
   `Path`.
5. Add **one** stringification boundary in `wanda/session.py` and
   `wanda/create_scenario.py`:

   ```python
   model = pywanda.WandaModel(str(path), str(spec.wanda_bin))
   ```

**Verify.**

- `mypy` clean on `src/pywandahydra/`.
- All unit tests pass (the validators still accept `str` input from
  YAML; only the *internal* type changed).
- `grep` shows no remaining `str | Path` in `config/`.

**Risk / Rollback.** Low â€” purely internal type tightening. Rollback: revert
the commit; nothing else depends on the new types.

---

## Step 2 â€” Library-friendly logging  (Â§3.12)

**Goal.** Stop touching the root logger and the module-level `LOG_LEVEL`
global.

**Changes.**

- Rewrite [src/pywandahydra/app_logging.py](../../src/pywandahydra/app_logging.py):
  - Drop the `LogLevel` enum; accept a `str | int` and resolve with
    `logging.getLevelName(str(level).upper())`.
  - Install handlers on `logging.getLogger("pywandahydra")`, not the
    root logger.
  - Remove the module-level `LOG_LEVEL` global; if a caller needs it,
    `logging.getLogger("pywandahydra").level` is the source of truth.
  - Keep `coloredlogs` as the colour backend, behind a `colors: bool`
    flag.
- Update `cli/commands.py` `setup_logging(LogLevel.parse(...))` call
  sites to use the new signature.

**Verify.** CLI still produces coloured output; no other logger
configuration interferes with library users embedding `pywandahydra`.

**Risk / Rollback.** Trivial.

---

## Step 3 â€” Fix known minor schema/typing issues  (Â§3.16)

**Goal.** Clear out the small but real bugs before deeper refactors land
on top.

**Changes.**

1. `wanda/create_scenario.py`: reorder `prepare_scenario_model` parameters
   so positional args precede `*, readonly`. Document which arguments are
   keyword-only. Update all call sites.
2. `postprocessing/plotting/models.py` - `AxisSpec.label`: pick one of:
   - `label: str | None = None` *(preferred - matches actual default)*;
   - `label: str = ""`.
   Update consumers accordingly.
3. `postprocessing/plotting/styles/layout.py` - fix the `PageMetadata`
   name typo (rename via the language server so all references update).
4. `execution/case_plan.py` `_compute_hash`:
   - Drop `case_id` from the hashed payload (renaming a scenario should
     not invalidate resume).
   - Add `sha256(model_file_bytes)` of the **base** model so a changed
     model file forces a re-run even if the YAML is unchanged.
   - Keep the version key in the hash (`"v": 2`) so old caches are
     transparently invalidated.

**Verify.** Unit tests in `unit_test/execution/test_resume_policy.py`
extended to cover both rename-invariance and model-mutation invalidation.

**Risk / Rollback.** Bumping the hash schema invalidates existing run
directories (they will be re-executed once on first run after the
upgrade). Acceptable for a pre-1.0 package; document in `CHANGELOG.md`.

---

## Step 4 â€” Adapter pattern: own the full WANDA surface  (Â§3.1, Â§3.11)

**Goal.** The worker must import nothing from `pywanda`. Every WANDA call
goes through `WandaAdapter`.

**Why.** Without this, the post-processing plugin model is window-dressing
â€” core execution stays Windows-only and untestable in CI.

**Changes.**

1. Grow `WandaAdapter` in
   [src/pywandahydra/wanda/adapter.py](../../src/pywandahydra/wanda/adapter.py)
   to cover the *full* lifecycle:

   ```python
   class WandaAdapter(Protocol):
       def session(self, spec: ModelSpecification, model_path: Path
                   ) -> AbstractContextManager[ModelHandle]: ...
       def prepare_scenario_model(self, base: Path, scenario_dir: Path,
                                  scenario_name: str, *, readonly: bool) -> Path: ...
       def apply(self, h: ModelHandle, change: ParameterChange) -> None: ...
       def save_input(self, h: ModelHandle) -> None: ...
       def run_steady(self, h: ModelHandle) -> None: ...
       def run_unsteady(self, h: ModelHandle) -> None: ...
       def simulation_time(self, h: ModelHandle) -> float: ...
       # existing extract helpers stay
   ```

   `ModelHandle = Any` (opaque to callers).
2. Move `wanda_session` body into `PywandaAdapter.session()` (this is the
   single place that calls `pywanda.WandaModel(str(path), str(bin))` â€”
   the **only** legitimate `str(Path)` boundary; see Â§3.9 answer).
3. Move `apply_parameter_change`, `prepare_scenario_model` invocations
   behind adapter methods. The free functions in `wanda/api.py` stay
   (they're the implementation), but only the adapter is allowed to
   import them.
4. Rewrite [src/pywandahydra/execution/worker.py](../../src/pywandahydra/execution/worker.py)
   to import **only** `pywandahydra.wanda.adapter`:
   - Resolve `adapter_class` from a string on `CasePlan` (see Â§3.1
     answer): `module, _, attr = path.partition(":"); cls = getattr(import_module(module), attr); adapter = cls()`.
   - All `pywanda` symbols disappear from worker.
5. Add `unit_test/wanda/fakes.py` â€” an in-memory `FakeWandaAdapter` that
   returns canned numpy arrays and a stub `ModelHandle`. Add tests for
   `worker.run_one_case` that use it (no `pywanda` import required).

**Serializability check (answer to Â§3.1).** `PywandaAdapter` is stateless,
so it pickles trivially. The convention is: `CasePlan.adapter_class` is a
**string** (`"pywandahydra.wanda.pywanda_adapter:PywandaAdapter"`) â€” the
adapter *instance* never travels through the pool. Each worker
instantiates its own. The `ModelHandle` is created and disposed inside
the worker and never crosses a process boundary.

**Verify.**

- `grep "import pywanda" src/pywandahydra/execution/` returns nothing.
- New `test_worker_with_fake_adapter.py` runs on Linux CI without
  `pywanda` installed.

**Risk / Rollback.** Medium â€” touches the hot path. Mitigation: the real
`PywandaAdapter` is unchanged in behaviour; we only re-route call sites.
Add an integration test (Windows-only marker) that exercises the full
real-WANDA path once before merging.

---

## Step 5 â€” Merge `plots/` into `plotting/`  (Â§3.6)

**Goal.** One plotting package with obvious structure.

**Changes.**

1. Move files (use `git mv` so history follows):
   ```
   postprocessing/plots/renderer.py  ->  postprocessing/plotting/renderers/
   ```
2. Remove the `postprocessing/plots/` package entirely; the merged
   `postprocessing/plotting/` becomes the only home.
3. Use the language-server rename to update every `from ..plots...`
   import to `from ..plotting...`.

**Verify.** `grep -r "postprocessing.plots" src/ unit_test/` returns
nothing. Tests pass.

**Risk / Rollback.** Pure rename; revert is mechanical.

### Step 5b â€” Themeable, extensible plotting  (Â§3.6)

**Goal.** Allow external/adjustable `PlotTheme` without forking the
renderer.

**Changes.**

1. Keep `PlotTheme` as a `frozen=True` dataclass in
   `postprocessing/plotting/renderers/theme.py`.
2. Add a small theme registry in
   `postprocessing/plotting/theme_registry.py`:

   ```python
   _THEMES: dict[str, PlotTheme] = {}

   def register_theme(name: str, theme: PlotTheme) -> None:
       _THEMES[name] = theme

   def get_theme(name: str) -> PlotTheme:
       try:
           return _THEMES[name]
       except KeyError as exc:
           raise KeyError(f"Unknown theme '{name}'. Known: {sorted(_THEMES)}") from exc

   def resolve_theme(spec: ThemeSpec | None) -> PlotTheme:
       if spec is None:
           return get_theme("default")
       base = get_theme(spec.name)
       return dataclasses.replace(base, **spec.overrides)
   ```

3. `ThemeSpec` is a Pydantic model in `config/models.py`:

   ```python
   class ThemeSpec(BaseModel):
       model_config = ConfigDict(extra="forbid")
       name: str = "default"
       overrides: dict[str, Any] = Field(default_factory=dict)
   ```

4. Register `default` and `deltares_light` themes at module import in
   `theme_registry.py` (pure data - no import side effects beyond filling a dict).
5. Renderer accepts a `PlotTheme` instance; never reads YAML directly.
6. Entry-point hook for external themes (mirrors Â§6):

   ```toml
   [project.entry-points."pywandahydra.themes"]
   corp_dark = "my_pkg.themes:CORP_DARK"
   ```

**Verify.** A new `unit_test/postprocessing/plotting/test_themes.py`:
register a theme, resolve via `ThemeSpec(name=..., overrides={...})`,
assert `dataclasses.replace` semantics.

**Risk / Rollback.** Low â€” purely additive.

---

## Step 6 â€” Workflow is the only post-processing entry point  (Â§3.2, Â§3.7)

**Goal.** Delete the duplicate `_STEPS` registry and the import-time
`register_step` side effects.

**Changes.**

1. In [src/pywandahydra/postprocessing/pipeline.py](../../src/pywandahydra/postprocessing/pipeline.py):
   - Delete `_STEPS`, `register_step`, `get_steps`, `clear_steps`.
   - Make `workflow` a **required** argument of `run_postprocessing`.
2. In [src/pywandahydra/postprocessing/steps/](../../src/pywandahydra/postprocessing/steps/):
   - Remove the `register_step(...)` call at the bottom of
     `summary_table.py` and `route_plots.py`.
   - Steps are now inert on import.
3. Defer matplotlib imports (`pyplot`, `PdfPages`) to inside `run()` so
   `pywandahydra status` doesn't pay the import cost.
4. `unit_test/postprocessing/`: remove any `clear_steps()` calls; rely on
   workflow objects passed explicitly.

**Verify.** Importing `pywandahydra.postprocessing.steps.summary_table`
does **not** mutate any module-level dict. `pywandahydra status` is
measurably faster.

**Risk / Rollback.** Anyone calling `register_step` externally is broken
â€” but nothing in this repo does, and the package is pre-1.0. Note in
`CHANGELOG.md`.

---

## Step 7 â€” `RunStep` protocol + move run-level aggregation out of the runner  (Â§3.5)

**Goal.** No post-processing import in `execution/runner.py`.

**Changes.**

1. In `postprocessing/protocols.py` (new file â€” see Step 9):

   ```python
   @runtime_checkable
   class CaseStep(Protocol):
       name: ClassVar[str]
       def applicable(self, ctx: CaseContext) -> bool: ...
       def run(self, ctx: CaseContext) -> None: ...

   @runtime_checkable
   class RunStep(Protocol):
       name: ClassVar[str]
       def run(self, ctx: PostProcessingRunContext) -> None: ...
   ```

2. `PostProcessingRunContext` (dataclass) bundles `run_root`, `run_id`, and a
   read-only iterable of per-case results.
3. Extend `Workflow` protocol with `run_steps(ctx)` returning
   `list[RunStep]` (alongside `case_steps`).
4. Move the bodies of `merge_case_figure_pdfs` and `aggregate_tables`
   into two `RunStep` implementations: `MergePdfsStep`, `AggregateTablesStep`.
5. `DefaultWorkflow.run_steps()` returns
   `[AggregateTablesStep(), MergePdfsStep()]`.
6. In [runner.py](../../src/pywandahydra/execution/runner.py):
   - Delete the inline `if n_success > 0: ... aggregate_tables / merge_...`
     block.
   - After the worker pool drains:
     ```python
     for step in workflow.run_steps(rsctx):
         try: step.run(rsctx)
         except Exception: logger.exception("Run step %r failed", step.name)
     ```

**Verify.** `grep "from ..postprocessing" src/pywandahydra/execution/runner.py`
returns nothing. Run-level outputs (merged PDF, summary tables) are
byte-identical to the previous behaviour for the same input.

**Risk / Rollback.** Medium â€” the aggregation order matters. Add an
integration test that runs the example config end-to-end (mocked
adapter) and checks for the expected files.

---

## Step 8 â€” Configurable workflows (Pydantic `Params`)  (Â§3.4)

**Goal.** Workflows are first-class configurable objects.

**Changes.**

1. Update the `Workflow` protocol:

   ```python
   class Workflow(Protocol):
       name: ClassVar[str]
       description: ClassVar[str]
       Params: ClassVar[type[BaseModel]]
       def __init__(self, params: BaseModel) -> None: ...
       def case_steps(self, ctx: CaseContext) -> list[CaseStep]: ...
       def run_steps(self, ctx: PostProcessingRunContext) -> list[RunStep]: ...
   ```

2. Replace `ExecutionConfig.workflow: str` with a discriminated
   wrapper:

   ```python
   class WorkflowSpec(BaseModel):
       model_config = ConfigDict(extra="forbid")
       name: str = "default"
       params: dict[str, Any] = Field(default_factory=dict)

   class ExecutionConfig(BaseModel):
       workflow: WorkflowSpec = Field(default_factory=WorkflowSpec)
       ...
   ```

   Accept a bare string for back-compat with a `model_validator(mode="before")`:

   ```python
   @model_validator(mode="before")
   @classmethod
   def _coerce_str(cls, data):
       if isinstance(data.get("workflow"), str):
           data["workflow"] = {"name": data["workflow"]}
       return data
   ```

3. Resolution helper:

   ```python
   def resolve_workflow(spec: WorkflowSpec) -> Workflow:
       cls = get_workflow_class(spec.name)
       params = cls.Params.model_validate(spec.params)
       return cls(params)
   ```

4. Built-in **composed** workflow â€” the no-code path for YAML/XLS users
   (Â§3.4 answer):

   ```python
   class ConfigDrivenWorkflow:
       name = "composed"
       class Params(BaseModel):
           case_steps: list[StepSpec] = []
           run_steps: list[StepSpec] = []
       def case_steps(self, ctx): return [build_step(s) for s in self._p.case_steps]
       def run_steps(self, ctx): return [build_run_step(s) for s in self._p.run_steps]
   ```

   Where `StepSpec = {name: str, params: dict[str, Any]}` and there's a
   parallel **step registry** (`register_case_step`, `register_run_step`)
   keyed by step name, each step exposing its own `Params` class.

5. XLS input: extend the existing scenario source registry so a
   `Workflow` sheet (if present) is parsed into the same
   `WorkflowSpec` model.

**Verify.** Unit tests for `WorkflowSpec` (bare string accepted),
`resolve_workflow` (rejects unknown name, rejects extra params),
`ConfigDrivenWorkflow` (renders a real run with two steps from YAML
only).

**Risk / Rollback.** Public-config change but covered by the
`model_validator` shim. Document in `CHANGELOG.md`.

---

## Step 9 â€” Plugin discovery via entry points  (Â§3.3)

**Goal.** Third parties can register workflows, steps, themes, and
scenario sources by installing a wheel.

**Changes.**

1. New file `postprocessing/registry.py` (consolidates the three
   workflow/case-step/run-step registries):

   ```python
   from importlib.metadata import entry_points

   _METHOD_CLASSES: dict[str, type[Workflow]] = {}
   _CASE_STEPS:     dict[str, type[CaseStep]]    = {}
   _RUN_STEPS:      dict[str, type[RunStep]]     = {}

   def bootstrap() -> None:
       _register_builtins()
       _load_group("pywandahydra.workflows", _METHOD_CLASSES)
       _load_group("pywandahydra.case_steps",    _CASE_STEPS)
       _load_group("pywandahydra.run_steps",     _RUN_STEPS)

   def _load_group(group: str, target: dict[str, type]) -> None:
       for ep in entry_points(group=group):
           try:
               cls = ep.load()
               target[cls.name] = cls
           except Exception:
               logger.exception("Failed to load %s plugin %r", group, ep.name)
   ```

2. Declare built-in entry points in `pyproject.toml` so the *first-party*
   workflows/steps load through the same mechanism as third-party
   ones (no special-case code path):

   ```toml
   [project.entry-points."pywandahydra.workflows"]
   default  = "pywandahydra.postprocessing.workflows.default:DefaultWorkflow"
   composed = "pywandahydra.postprocessing.workflows.composed:ConfigDrivenWorkflow"

   [project.entry-points."pywandahydra.case_steps"]
   summary_table = "pywandahydra.postprocessing.steps.summary_table:SummaryTableStep"
   route_plots   = "pywandahydra.postprocessing.steps.route_plots:RoutePlotStep"

   [project.entry-points."pywandahydra.run_steps"]
   aggregate_tables = "pywandahydra.postprocessing.steps.aggregate_tables:AggregateTablesStep"
   merge_pdfs       = "pywandahydra.postprocessing.steps.merge_pdfs:MergePdfsStep"
   ```

3. `bootstrap()` is called once at CLI entry and once per worker (already
   idempotent).
4. CLI: add `pywandahydra plugins` subcommand that prints all registered
   workflows/steps/themes and their `Params` schemas (great for
   onboarding and Â§3.14).

**Example: shipping a third-party workflow (Â§3.3 answer).**

```toml
# downstream package "wanda-surge-pack"
[project]
dependencies = ["pywanda-hydra"]

[project.entry-points."pywandahydra.workflows"]
surge = "wanda_surge_pack.workflows:SurgeWorkflow"
```

```python
# wanda_surge_pack/workflows.py
class SurgeWorkflow:
    name = "surge"
    description = "Pressure surge focused report"
    class Params(BaseModel):
        include_envelope: bool = True

    def __init__(self, params): self._p = params
    def case_steps(self, ctx): ...
    def run_steps(self, ctx): return []
```

```yaml
# user's run_config.yaml
execution:
  workflow:
    name: surge
    params: { include_envelope: true }
```

**Verify.** `pywandahydra plugins` lists all built-ins. A dummy
`unit_test/postprocessing/test_entry_points.py` registers a fake plugin
via `EntryPoint.load`-style monkeypatch and asserts it's discoverable.

**Risk / Rollback.** Low â€” entry points are stdlib and failures only
emit a log line.

---

## Step 10 â€” Reconcile workflow vs `enabled_steps`  (Â§3.10)

**Goal.** Make the two filters explicit and validated.

**Changes.**

1. In the runner, after resolving `workflow.case_steps(ctx)`, compute:

   ```python
   catalogue = {s.name for s in workflow.case_steps(case_ctx)}
   requested = set(scenario.post_processing.enabled_steps)
   unknown = requested - catalogue
   if unknown:
       raise ValueError(
           f"Scenario '{scenario.meta.name}' enables steps "
           f"{sorted(unknown)} not provided by workflow "
           f"'{workflow.name}'. Available: {sorted(catalogue)}"
       )
   ```

2. Document the contract in
   [scenarios/schema.py](../../src/pywandahydra/scenarios/schema.py)
   `PostProcessingConfig.enabled_steps`: "allow-list **within the
   resolved workflow's catalogue**; empty = run all applicable steps
   from the workflow".

3. Each step's `applicable()` keeps the `enabled_steps` check â€” it stays
   the single point that decides per-scenario opt-out â€” but the runner
   guarantees the names are valid up front so failures are loud, not
   silent.

**Verify.** Unit test: scenario with `enabled_steps=["does_not_exist"]`
under `default` workflow raises `ValueError` with the unknown name.

**Risk / Rollback.** Surfaces previously-silent misconfigurations as
errors. Bump major version of the config schema. Add the new failure
case to `pywandahydra validate`.

---

## Step 11 â€” Curated public API and CLI polish

**Goal.** The package has a small, documented surface so external code
knows what's stable.

**Changes.**

1. Replace [src/pywandahydra/\_\_init\_\_.py](../../src/pywandahydra/__init__.py)
   with a curated re-export block:

   ```python
   from .config.loader import RunConfig, load_run_config
   from .execution.runner import RunResult, run
   from .postprocessing.context import CaseContext, PostProcessingRunContext
   from .postprocessing.protocols import CaseStep, Workflow, RunStep
   from .postprocessing.registry import (
       bootstrap,
       register_case_step,
       register_workflow,
       register_run_step,
   )
   from .postprocessing.plotting.theme_registry import register_theme
   from .postprocessing.plotting.renderers.theme import PlotTheme

   __all__ = [
       "RunConfig", "load_run_config", "run", "RunResult",
       "CaseContext", "PostProcessingRunContext",
       "CaseStep", "RunStep", "Workflow",
       "bootstrap", "register_workflow", "register_case_step",
       "register_run_step", "PlotTheme", "register_theme",
   ]
   ```

2. Add a `pywandahydra plugins` CLI command (shipped in Step 9) and a
   `pywandahydra config-schema` command that dumps the JSON schema of
   `RunConfig` for editor integration.
3. Skipped: full README rewrite and integration-test suite (deferred per
   user direction).

**Verify.** `from pywandahydra import Workflow, register_workflow`
works. `mypy --strict src/pywandahydra/__init__.py` passes.

**Risk / Rollback.** Pure addition.

---

## Target architecture (end state)

```
pywandahydra/
â”œâ”€â”€ __init__.py                  # curated re-exports
â”œâ”€â”€ app_logging.py               # library-friendly, no globals
â”œâ”€â”€ cli/
â”‚   â””â”€â”€ commands.py              # typer; thin over the service layer
â”œâ”€â”€ config/
â”‚   â”œâ”€â”€ models.py                # Pydantic models, Path-typed
â”‚   â””â”€â”€ loader.py                # YAML/JSON â†’ RunConfig
â”œâ”€â”€ scenarios/
â”‚   â”œâ”€â”€ schema.py                # ParameterChange, ScenarioSpecification, ...
â”‚   â”œâ”€â”€ mapper.py
â”‚   â””â”€â”€ sources/                 # registry + entry_points
â”‚       â”œâ”€â”€ base.py
â”‚       â””â”€â”€ xls.py
â”œâ”€â”€ wanda/
â”‚   â”œâ”€â”€ adapter.py               # Protocol: session + ops + extract
â”‚   â”œâ”€â”€ pywanda_adapter.py       # the ONE place str(Path) hits pywanda
â”‚   â”œâ”€â”€ api.py                   # low-level helpers used by the adapter
â”‚   â””â”€â”€ create_scenario.py
â”œâ”€â”€ execution/
â”‚   â”œâ”€â”€ case_plan.py             # CasePlan carries adapter_class: str
â”‚   â”œâ”€â”€ journal.py
â”‚   â”œâ”€â”€ artifacts.py
â”‚   â”œâ”€â”€ worker.py                # imports only wanda.adapter
â”‚   â””â”€â”€ runner.py                # imports only postprocessing.protocols/registry
â””â”€â”€ postprocessing/
    â”œâ”€â”€ context.py               # CaseContext, PostProcessingRunContext
    â”œâ”€â”€ protocols.py             # CaseStep, RunStep, Workflow
    â”œâ”€â”€ registry.py              # entry_points discovery + register_* helpers
    â”œâ”€â”€ cache.py                 # ParquetCache
    â”œâ”€â”€ extract.py
    â”œâ”€â”€ workflows/
    â”‚   â”œâ”€â”€ default.py
    â”‚   â””â”€â”€ composed.py          # YAML/XLS-defined composition
    â”œâ”€â”€ steps/                   # inert on import; one file per step
    â”‚   â”œâ”€â”€ summary_table.py
    â”‚   â”œâ”€â”€ route_plots.py
    â”‚   â”œâ”€â”€ aggregate_tables.py
    â”‚   â””â”€â”€ merge_pdfs.py
    â””â”€â”€ plotting/                # merged; only plotting package
        â”œâ”€â”€ renderer.py
        â”œâ”€â”€ themes.py            # PlotTheme + registry
        â”œâ”€â”€ specifications.py
        â”œâ”€â”€ styles/
        â””â”€â”€ image_data/
```

**Plugin contract recap.** A downstream wheel registers via entry points
under `pywandahydra.workflows`, `pywandahydra.case_steps`,
`pywandahydra.run_steps`, `pywandahydra.themes`, or
`pywandahydra.scenario_sources`. No code changes in `pywanda-hydra`
needed to add new post-processing routines.

---

## Shipping order summary

| Step | Touches | Risk | Why first |
|------|---------|------|-----------|
| 1    | config types, `RunResult`              | Low    | unlocks `Path`-clean code paths |
| 2    | logging                                | Low    | independent, removes globals |
| 3    | small bug fixes                        | Low    | clear the deck |
| 4    | adapter + worker                       | Medium | unlocks CI testability |
| 5/5b | plotting rename + themes               | Low    | mechanical, prepares Step 7 |
| 6    | delete `_STEPS`                        | Low    | now safe because nobody uses it |
| 7    | RunStep + move run-level aggregation   | Medium | makes runner extensible |
| 8    | configurable workflows (`Params`)  | Medium | enables YAML/XLS composition |
| 9    | entry_points discovery                 | Low    | the headline of the architecture |
| 10   | workflow vs `enabled_steps`         | Low    | turns silent misconfig into errors |
| 11   | curated `__init__.py` + plugins CLI    | Low    | external contract |


