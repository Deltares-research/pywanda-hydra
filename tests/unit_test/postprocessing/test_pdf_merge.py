"""Unit tests for postprocessing.io.pdf_merge."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import matplotlib.pyplot as plt
from pypdf import PdfReader  # noqa: E402

from pywandahydra.postprocessing.figures.run_pdf import merge_case_figure_pdfs  # noqa: E402


def _make_pdf(path: Path) -> None:
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    fig.savefig(path)
    plt.close(fig)


class TestMergeCaseFigurePdfs(unittest.TestCase):
    def test_returns_none_when_scenarios_dir_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scenarios_dir = Path(tmp_dir) / "does_not_exist"
            output_path = Path(tmp_dir) / "merged.pdf"

            result = merge_case_figure_pdfs(scenarios_dir, output_path)

            self.assertIsNone(result)
            self.assertFalse(output_path.exists())

    def test_returns_none_when_scenarios_path_is_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scenarios_path = Path(tmp_dir) / "scenarios"
            scenarios_path.write_text("not a directory")
            output_path = Path(tmp_dir) / "merged.pdf"

            result = merge_case_figure_pdfs(scenarios_path, output_path)

            self.assertIsNone(result)

    def test_returns_none_when_no_case_has_figures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scenarios_dir = Path(tmp_dir) / "scenarios"
            scenarios_dir.mkdir()
            (scenarios_dir / "case_1").mkdir()
            output_path = Path(tmp_dir) / "merged.pdf"

            result = merge_case_figure_pdfs(scenarios_dir, output_path)

            self.assertIsNone(result)

    def test_returns_none_when_figures_dir_has_no_pdfs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scenarios_dir = Path(tmp_dir) / "scenarios"
            figures_dir = scenarios_dir / "case_1" / "figures"
            figures_dir.mkdir(parents=True)
            (figures_dir / "notes.txt").write_text("hello")
            output_path = Path(tmp_dir) / "merged.pdf"

            result = merge_case_figure_pdfs(scenarios_dir, output_path)

            self.assertIsNone(result)

    def test_merges_multiple_case_figure_pdfs_in_sorted_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scenarios_dir = Path(tmp_dir) / "scenarios"

            case1_figures = scenarios_dir / "case_1" / "figures"
            case2_figures = scenarios_dir / "case_2" / "figures"
            case1_figures.mkdir(parents=True)
            case2_figures.mkdir(parents=True)

            _make_pdf(case1_figures / "b_fig.pdf")
            _make_pdf(case1_figures / "a_fig.pdf")
            _make_pdf(case2_figures / "c_fig.pdf")

            output_path = Path(tmp_dir) / "output" / "merged.pdf"

            result = merge_case_figure_pdfs(scenarios_dir, output_path)

            self.assertEqual(result, output_path)
            self.assertTrue(output_path.exists())

            reader = PdfReader(str(output_path))
            self.assertEqual(len(reader.pages), 3)

    def test_skips_case_dirs_without_figures_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scenarios_dir = Path(tmp_dir) / "scenarios"
            case1_figures = scenarios_dir / "case_1" / "figures"
            case1_figures.mkdir(parents=True)
            _make_pdf(case1_figures / "fig.pdf")

            # case_2 has no figures dir at all
            (scenarios_dir / "case_2").mkdir()

            # a plain file at scenarios_dir level should be ignored (not a dir)
            (scenarios_dir / "readme.txt").write_text("hello")

            output_path = Path(tmp_dir) / "merged.pdf"

            result = merge_case_figure_pdfs(scenarios_dir, output_path)

            self.assertEqual(result, output_path)
            reader = PdfReader(str(output_path))
            self.assertEqual(len(reader.pages), 1)


if __name__ == "__main__":
    unittest.main()
