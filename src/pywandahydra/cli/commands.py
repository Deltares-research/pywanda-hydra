"""CLI commands for pywandahydra - run, status, validate, plot."""

from __future__ import annotations

import faulthandler
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

    from ..run import execute_run, prepare_run

    try:
        plan = prepare_run(config, workers=workers, resume=True if resume else None, preflight=True)
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Invalid run configuration: {e}", err=True)
        raise typer.Exit(code=1) from None
    logger.info("Prepared %d included cases", len(plan.cases))
    result = execute_run(plan)

    # Summary
    typer.echo(
        f"\nRun complete: {result.n_success} succeeded, "
        f"{result.n_failed} failed, {result.n_skipped} skipped"
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
    from ..execution.status import CaseStatusStore

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
        state = CaseStatusStore(case_dir).read()
        if state is None:
            typer.echo(f"{case_dir.name:<30} {'UNKNOWN':<12} {'-':<12} {'-':<10}")
            continue

        duration = f"{state.duration_s:.1f}s" if state.duration_s else "-"
        error = (state.error_summary or "")[:40]
        typer.echo(
            f"{state.case_id:<30} {state.simulation_status:<12} "
            f"{state.postprocessing_status:<12} {duration:<10} {error}"
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
    from ..run import validate_run

    try:
        plan = validate_run(config)
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"Config INVALID: {e}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(
        f"Config OK: run_id={plan.configuration.run_id}, "
        f"workers={plan.configuration.execution.workers}"
    )
    typer.echo(
        f"Scenarios OK: {len(plan.scenario_document.scenarios)} total, {len(plan.cases)} included"
    )
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
    """Render plots from durable result data (no WANDA required)."""
    from ..postprocessing.plotting.renderers.route_plot import render_route_plot
    from ..results import ParquetResultStore

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
        store = ParquetResultStore(case_dir / "results")
        if not store.is_complete():
            typer.echo(f"  {case_dir.name}: no complete result data - skipping")
            continue

        figures_dir = case_dir / "figures"
        typer.echo(f"  {case_dir.name}: rendering plots...")

        # Build export props from requested format
        from ..postprocessing.figures.export import build_figure_export_props

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
                render_route_plot(spec, store, output_dir=figures_dir, export_props=export_props)
        else:
            inventory = store.inventory()
            route_identities = sorted(
                {item.route for item in inventory.route_products} if inventory else set()
            )
            for identity in route_identities:
                from ..scenarios import RoutePlotSpecification
                from ..scenarios.models.plot_axis import AxisSpecification

                spec = RoutePlotSpecification(
                    route_id=identity.route_id,
                    property=identity.property,
                    title=f"{identity.route_id}_{identity.property}",
                    x_axis=AxisSpecification(label="Distance [m]"),
                    y_axis=AxisSpecification(label=""),
                )
                render_route_plot(spec, store, output_dir=figures_dir, export_props=export_props)

    typer.echo("Plotting complete.")
