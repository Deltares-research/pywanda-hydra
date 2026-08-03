"""CLI commands for pywandahydra - run, status, validate, plot."""

from __future__ import annotations

import faulthandler
import json
import logging
from pathlib import Path

import typer

from ..app_logging import setup_logging

app = typer.Typer(
    name="pywandahydra",
    help="Orchestrate multiple WANDA simulations via pywanda.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@app.command()
def run(
    config: Path = typer.Argument(
        ..., help="Path to the run configuration file (.yaml or .json).", exists=True
    ),
    workers: int | None = typer.Option(None, "--workers", "-w", help="Override number of workers."),
    resume: bool = typer.Option(False, "--resume", "-r", help="Skip already-completed cases."),
    log_level: str = typer.Option(
        "INFO", "--log-level", "-l", help="Log level (DEBUG, INFO, WARNING, ERROR)."
    ),
) -> None:
    """Run WANDA scenarios from a configuration file."""
    # Dump the Python stack to stderr on a native crash (access violation in
    # pywanda/WANDA DLLs kills the process without a traceback otherwise).
    faulthandler.enable()

    setup_logging(log_level)
    logger = logging.getLogger(__name__)

    from ..config.loader import (
        RunMetadata,
        apply_post_processing_overrides,
        build_run_context,
        load_run_config,
        validate_run_paths,
    )
    from ..execution.runner import run as run_scenarios
    from ..scenarios.loader import load_scenario_document
    from ..wanda.validation import assert_preflight_valid

    # Load and validate config
    try:
        cfg = load_run_config(config)
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Error loading config: {e}", err=True)
        raise typer.Exit(code=1) from None

    # Apply CLI overrides
    if workers is not None:
        if workers < 1:
            typer.echo("--workers must be >= 1", err=True)
            raise typer.Exit(code=1)
        cfg.execution.n_workers = workers

    if resume:
        cfg.execution.resume = True

    # Validate runtime paths before loading scenarios/executing.
    try:
        validate_run_paths(cfg, config_dir=config.parent)
    except ValueError as e:
        typer.echo(f"Invalid runtime configuration: {e}", err=True)
        raise typer.Exit(code=1) from None

    # Load scenarios from the scenario file
    # (validate_run_paths already resolved scenario_file against the config dir)
    scenario_path = cfg.scenario_file

    try:
        scenario_document = load_scenario_document(scenario_path)
        scenarios = list(scenario_document.scenarios)
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Error loading scenarios: {e}", err=True)
        raise typer.Exit(code=1) from None

    try:
        assert_preflight_valid(model_spec=cfg.model, scenarios=scenarios)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None

    try:
        apply_post_processing_overrides(cfg, scenarios)
    except ValueError as e:
        typer.echo(f"Invalid post_processing config: {e}", err=True)
        raise typer.Exit(code=1) from None

    logger.info(
        "Loaded %d scenarios from %s (%d included)",
        len(scenarios),
        scenario_path.name,
        sum(1 for s in scenarios if s.include),
    )

    # Build run context
    ctx = build_run_context(cfg)
    # Bridge analysis metadata from the scenario document onto the run context
    # (temporary path until Slice 07's RunPlan owns it).
    ctx.analysis_meta = scenario_document.analysis_metadata

    # Write run metadata
    from ..execution.artifacts import create_run_directories

    run_root = Path(ctx.root_dir)
    create_run_directories(ctx, config_path=config, scenario_file=scenario_path)
    run_metadata = RunMetadata()
    metadata_path = run_root / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(run_metadata.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )

    # Execute
    result = run_scenarios(
        model=cfg.model,
        ctx=ctx,
        scenarios=scenarios,
        n_workers=cfg.execution.n_workers,
        resume=cfg.execution.resume,
        workflow_name=cfg.execution.workflow.name,
        workflow_params=cfg.execution.workflow.params,
    )

    # Summary
    typer.echo(
        f"\nRun complete: {result.n_success} succeeded, "
        f"{result.n_failed} failed, {result.n_skipped} skipped "
        f"(of {result.n_selected} selected / {result.n_total} total)"
    )
    if result.n_failed > 0:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@app.command()
def status(
    run_dir: Path = typer.Argument(..., help="Path to the run output directory.", exists=True),
) -> None:
    """Show status of all cases in a run directory."""
    from ..execution.journal import CaseJournal

    scenarios_dir = run_dir / "scenarios"
    if not scenarios_dir.exists():
        typer.echo("No scenarios directory found.", err=True)
        raise typer.Exit(code=1)

    case_dirs = sorted(d for d in scenarios_dir.iterdir() if d.is_dir())

    if not case_dirs:
        typer.echo("No cases found.")
        return

    typer.echo(f"{'Case ID':<30} {'Status':<12} {'PP Status':<12} {'Duration':<10} {'Error'}")
    typer.echo("-" * 90)

    for case_dir in case_dirs:
        journal = CaseJournal(case_dir)
        state = journal.read_state()
        if state is None:
            typer.echo(f"{case_dir.name:<30} {'UNKNOWN':<12} {'-':<12} {'-':<10}")
            continue

        duration = f"{state.duration_s:.1f}s" if state.duration_s else "-"
        error = (state.error or "")[:40]
        typer.echo(
            f"{state.case_id:<30} {state.status:<12} "
            f"{state.postprocess_status:<12} {duration:<10} {error}"
        )


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@app.command()
def validate(
    config: Path = typer.Argument(
        ..., help="Path to the configuration file to validate.", exists=True
    ),
) -> None:
    """Validate a configuration file without running anything."""
    from ..config.loader import load_run_config, validate_run_paths
    from ..scenarios.loader import assert_scenario_file_valid, load_scenario_document

    try:
        cfg = load_run_config(config)
        typer.echo(f"Config OK: run_id={cfg.run_id}, n_workers={cfg.execution.n_workers}")
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Config INVALID: {e}", err=True)
        raise typer.Exit(code=1) from None

    try:
        validate_run_paths(cfg, config_dir=config.parent)
    except ValueError as e:
        typer.echo(f"Runtime paths INVALID: {e}", err=True)
        raise typer.Exit(code=1) from None

    try:
        # validate_run_paths already resolved scenario_file against the config dir.
        assert_scenario_file_valid(cfg.scenario_file)
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Scenario file INVALID: {e}", err=True)
        raise typer.Exit(code=1) from None

    try:
        scenario_document = load_scenario_document(cfg.scenario_file)
        scenarios = list(scenario_document.scenarios)
        n_included = sum(1 for s in scenarios if s.include)
        typer.echo(f"Scenarios OK: {len(scenarios)} total, {n_included} included")
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Scenarios INVALID: {e}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo("Validation passed.")


# ---------------------------------------------------------------------------
# plot
# ---------------------------------------------------------------------------


@app.command()
def plot(
    run_dir: Path = typer.Argument(..., help="Path to the run output directory.", exists=True),
    case_id: str | None = typer.Option(
        None, "--case", "-c", help="Specific case ID to plot. Plots all if omitted."
    ),
    fmt: str = typer.Option("png", "--format", "-f", help="Output format (png, pdf, svg)."),
) -> None:
    """Render plots from cached extraction data (no WANDA required)."""
    from ..postprocessing.io.cache import ParquetCache
    from ..postprocessing.plotting.renderers.route_plot import render_route_plot

    scenarios_dir = run_dir / "scenarios"
    if not scenarios_dir.exists():
        typer.echo("No scenarios directory found.", err=True)
        raise typer.Exit(code=1)

    if case_id:
        case_dirs = [scenarios_dir / case_id]
        if not case_dirs[0].exists():
            typer.echo(f"Case not found: {case_id}", err=True)
            raise typer.Exit(code=1)
    else:
        case_dirs = sorted(d for d in scenarios_dir.iterdir() if d.is_dir())

    for case_dir in case_dirs:
        cache = ParquetCache(case_dir)
        if not cache.exists():
            typer.echo(f"  {case_dir.name}: no cached data - skipping")
            continue

        figures_dir = case_dir / "figures"
        typer.echo(f"  {case_dir.name}: rendering plots...")

        # Build export props from requested format
        from ..postprocessing.io.export import build_figure_export_props

        export_props = build_figure_export_props(
            include_pdf=(fmt == "pdf"),
            include_png=(fmt == "png"),
            include_svg=(fmt == "svg"),
        )

        # Load plot specs from post_process.json if available, else from cache
        pp_json = case_dir / "post_process.json"
        if pp_json.exists():
            import json as _json

            pp_data = _json.loads(pp_json.read_text(encoding="utf-8"))
            for spec_data in pp_data.get("route_plots", []):
                from ..scenarios import RoutePlotSpecification

                spec = RoutePlotSpecification.model_validate(spec_data)
                render_route_plot(spec, cache, output_dir=figures_dir, export_props=export_props)
        else:
            # Render all available routes from cache
            for route_title in cache.list_routes():
                from ..scenarios import RoutePlotSpecification
                from ..scenarios.models.plot_axis import AxisSpecification

                spec = RoutePlotSpecification(
                    route_id=route_title,
                    property="",
                    title=route_title,
                    x_axis=AxisSpecification(label="Distance [m]"),
                    y_axis=AxisSpecification(label=""),
                )
                render_route_plot(spec, cache, output_dir=figures_dir, export_props=export_props)

    typer.echo("Plotting complete.")

