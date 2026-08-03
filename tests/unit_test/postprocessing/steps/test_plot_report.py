"""Unit tests for postprocessing.steps.plot_report.PlotReportStep."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import matplotlib.pyplot as plt

from pywandahydra.postprocessing.core.context import CaseContext
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.postprocessing.steps.plot_report import PlotReportStep
from pywandahydra.scenarios import (
    FigurePostProcessingConfiguration,
    PostProcessingConfiguration,
    RoutePlotSpecification,
    ScenarioSpecification,
    TimeSeriesPlotSpecification,
)


def _make_ctx(tmp_path: Path, post_processing: PostProcessingConfiguration) -> CaseContext:
    scenario = ScenarioSpecification(
        number=1,
        include=True,
        name="case_001",
        post_processing=post_processing,
    )
    return CaseContext(cache=ParquetCache(tmp_path), scenario=scenario, case_dir=tmp_path)


class TestPlotReportStepApplicable(unittest.TestCase):
    def test_not_applicable_when_no_routes_or_time_plots(self) -> None:
        step = PlotReportStep()
        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir), PostProcessingConfiguration())

            self.assertFalse(step.applicable(ctx))

    def test_applicable_when_routes_present(self) -> None:
        step = PlotReportStep()
        pp = PostProcessingConfiguration(
            figures=FigurePostProcessingConfiguration(
                routes=[RoutePlotSpecification(route_id="Route A", property="Pressure", title="t")]
            )
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir), pp)

            self.assertTrue(step.applicable(ctx))

    def test_applicable_when_time_plots_present(self) -> None:
        step = PlotReportStep()
        pp = PostProcessingConfiguration(
            figures=FigurePostProcessingConfiguration(
                time_series=[
                    TimeSeriesPlotSpecification(component="PUMP P1", property="Head", title="t")
                ]
            )
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir), pp)

            self.assertTrue(step.applicable(ctx))


class TestPlotReportStepRun(unittest.TestCase):
    def test_run_writes_pdf_when_figures_rendered(self) -> None:
        step = PlotReportStep()
        pp = PostProcessingConfiguration(
            figures=FigurePostProcessingConfiguration(
                routes=[RoutePlotSpecification(route_id="Route A", property="Pressure", title="t")]
            )
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir), pp)

            fig = plt.figure()

            with mock.patch(
                "pywandahydra.postprocessing.steps.plot_report.render_combined_report_pages",
                return_value=[fig],
            ) as render_mock:
                step.run(ctx)

            self.assertTrue(render_mock.called)
            pdf_path = Path(tmp_dir) / "figures" / f"{Path(tmp_dir).name}.pdf"
            self.assertTrue(pdf_path.exists())

    def test_run_no_figures_does_not_write_pdf(self) -> None:
        step = PlotReportStep()
        pp = PostProcessingConfiguration(
            figures=FigurePostProcessingConfiguration(
                routes=[RoutePlotSpecification(route_id="Route A", property="Pressure", title="t")]
            )
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir), pp)

            with mock.patch(
                "pywandahydra.postprocessing.steps.plot_report.render_combined_report_pages",
                return_value=[],
            ):
                step.run(ctx)

            pdf_path = Path(tmp_dir) / "figures" / f"{Path(tmp_dir).name}.pdf"
            self.assertFalse(pdf_path.exists())


if __name__ == "__main__":
    unittest.main()

