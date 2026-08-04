"""Unit tests for the fixed post-processing pipeline."""

from __future__ import annotations

from unittest import mock

from pywandahydra.postprocessing.pipeline import (
    PostProcessingOutcome,
    process_case_results,
    process_run_results,
)
from pywandahydra.scenarios import (
    FigurePostProcessingConfiguration,
    MinMaxTableSpecification,
    PostProcessingConfiguration,
    RoutePlotSpecification,
    ScenarioSpecification,
)


def test_case_pipeline_skips_unconfigured_routines(make_case_ctx) -> None:
    ctx = make_case_ctx()

    outcomes = process_case_results(
        store=ctx.store,
        scenario=ctx.scenario,
        case_dir=ctx.case_dir,
    )

    assert outcomes == (
        PostProcessingOutcome(
            "case_minmax_table", "skipped", skip_reason="no MIN/MAX table specifications"
        ),
        PostProcessingOutcome("case_figure_pdf", "skipped", skip_reason="no figure specifications"),
    )


def test_case_pipeline_preserves_order_paths_and_independent_failures(make_case_ctx, tmp_path) -> None:
    ctx = make_case_ctx()
    scenario = ScenarioSpecification(
        number=1,
        include=True,
        name="case_001",
        post_processing=PostProcessingConfiguration(
            figures=FigurePostProcessingConfiguration(
                routes=[RoutePlotSpecification(route_id="route_1", property="Head")]
            )
        ),
    )
    figure_path = tmp_path / "case_001.pdf"

    scenario.post_processing.tables.minmax.append(
        MinMaxTableSpecification(component="PUMP P1", property="Head", mode="MAX")
    )

    with (
        mock.patch(
            "pywandahydra.postprocessing.pipeline.write_case_minmax_table",
            side_effect=RuntimeError("table failed"),
        ),
        mock.patch(
            "pywandahydra.postprocessing.pipeline.render_case_pdf",
            return_value=figure_path,
        ),
    ):
        outcomes = process_case_results(
            store=ctx.store,
            scenario=scenario,
            case_dir=ctx.case_dir,
        )

    assert [outcome.routine_name for outcome in outcomes] == [
        "case_minmax_table",
        "case_figure_pdf",
    ]
    assert outcomes[0].status == "failed"
    assert outcomes[0].error == "RuntimeError: table failed"
    assert outcomes[1].created_paths == (figure_path,)


def test_run_pipeline_captures_failures_and_skips_empty_output(tmp_path) -> None:
    run_root = tmp_path / "run_001"
    merged_pdf = run_root / "figures" / "run_001_merged.pdf"

    with (
        mock.patch(
            "pywandahydra.postprocessing.pipeline.write_run_minmax_table",
            side_effect=RuntimeError("table failed"),
        ),
        mock.patch(
            "pywandahydra.postprocessing.pipeline.merge_case_figure_pdfs",
            return_value=merged_pdf,
        ),
    ):
        outcomes = process_run_results(run_root=run_root, run_id="run_001")

    assert outcomes[0].routine_name == "run_minmax_table"
    assert outcomes[0].status == "failed"
    assert outcomes[0].error == "RuntimeError: table failed"
    assert outcomes[1] == PostProcessingOutcome(
        "run_figure_pdf", "succeeded", created_paths=(merged_pdf,)
    )
