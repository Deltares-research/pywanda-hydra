"""Thin command-line interface for the supported run API."""

from __future__ import annotations

import faulthandler
import logging
from pathlib import Path

import typer

from .app_logging import setup_logging

app = typer.Typer(
    name="pywandahydra",
    help="Orchestrate multiple WANDA simulations via pywanda.",
    no_args_is_help=True,
)


@app.command()
def run(
    config: Path = typer.Argument(
        ..., help="Path to the run configuration file (.yaml or .json).", exists=True
    ),
    workers: int | None = typer.Option(None, "--workers", "-w", help="Override number of workers."),
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume completed cases."),
    log_level: str = typer.Option(
        "INFO", "--log-level", "-l", help="Log level (DEBUG, INFO, WARNING, ERROR)."
    ),
) -> None:
    """Run WANDA scenarios from a configuration file."""
    faulthandler.enable()
    setup_logging(log_level)
    logger = logging.getLogger(__name__)

    from .run import execute_run, prepare_run

    try:
        plan = prepare_run(config, workers=workers, resume=True if resume else None, preflight=True)
    except (ValueError, FileNotFoundError) as error:
        typer.echo(f"Invalid run configuration: {error}", err=True)
        raise typer.Exit(code=1) from None
    logger.info("Prepared %d included cases", len(plan.cases))
    result = execute_run(plan)
    typer.echo(
        f"\nRun complete: {result.n_success} succeeded, "
        f"{result.n_failed} failed, {result.n_skipped} skipped"
    )
    if result.n_failed > 0:
        raise typer.Exit(code=1)


@app.command()
def validate(
    config: Path = typer.Argument(
        ..., help="Path to the configuration file to validate.", exists=True
    ),
) -> None:
    """Validate a configuration file without running anything."""
    from .run import validate_run

    try:
        report = validate_run(config)
    except (ValueError, FileNotFoundError) as error:
        typer.echo(f"Config INVALID: {error}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(
        f"Config OK: run_id={report.plan.configuration.run_id}, "
        f"workers={report.plan.configuration.execution.workers}"
    )
    typer.echo(
        f"Scenarios OK: {len(report.plan.scenario_document.scenarios)} total,"
        f" {len(report.plan.cases)} included"
    )
    typer.echo("Validation passed.")


@app.command()
def status(
    run_dir: Path = typer.Argument(..., help="Path to the run output directory.", exists=True),
) -> None:
    """Show status of all cases in a run directory."""
    from .run import read_run_status

    try:
        run_status = read_run_status(run_dir)
    except (ValueError, FileNotFoundError) as exception:
        typer.echo(f"Invalid run directory: {exception}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"{'Case ID':<30} {'Status':<12} {'PP Status':<12} {'Duration':<10} {'Error'}")
    typer.echo("-" * 90)
    for case_status in run_status.cases:
        if case_status is None:
            typer.echo(f"{'UNKNOWN':<30} {'UNKNOWN':<12} {'-':<12} {'-':<10}")
            continue
        duration = f"{case_status.duration_s:.1f}s" if case_status.duration_s else "-"
        error_summary = (case_status.error_summary or "")[:40]
        typer.echo(
            f"{case_status.case_id:<30} {case_status.simulation_status:<12} "
            f"{case_status.postprocessing_status:<12} {duration:<10} {error_summary}"
        )


@app.command()
def postprocess(
    run_dir: Path = typer.Argument(..., help="Path to the run output directory.", exists=True),
    case_ids: list[str] | None = typer.Option(
        None, "--case", "-c", help="Case ID to post-process; repeat to select multiple cases."
    ),
) -> None:
    """Regenerate configured outputs from committed simulation data."""
    from .run import postprocess_run

    try:
        result = postprocess_run(run_dir, case_ids=set(case_ids) if case_ids else None)
    except (ValueError, FileNotFoundError) as error:
        typer.echo(f"Post-processing failed: {error}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(
        f"Post-processing complete: {result.n_success} succeeded, "
        f"{result.n_failed} failed, {result.n_skipped} skipped"
    )
    if result.n_failed > 0:
        raise typer.Exit(code=1)
