"""Unit tests for postprocessing export helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

import pandas as pd  # noqa: E402

from pywandahydra.postprocessing.io.export import (  # noqa: E402
    DEFAULT_FIGURE_EXPORT_PROPS,
    DEFAULT_TABLE_EXPORT_PROPS,
    OPTIONAL_FIGURE_EXPORT_PROPS,
    build_figure_export_props,
    save_table,
    savefig,
)


class TestFigureExportDefaults(unittest.TestCase):
    def test_default_export_is_pdf_only(self) -> None:
        self.assertEqual(list(DEFAULT_FIGURE_EXPORT_PROPS.keys()), [".pdf"])

    def test_optional_formats_can_be_enabled_explicitly(self) -> None:
        export_props = build_figure_export_props(
            include_pdf=True, include_png=True, include_svg=True
        )

        self.assertEqual(list(export_props.keys()), [".pdf", ".png", ".svg"])
        self.assertEqual(export_props[".png"], OPTIONAL_FIGURE_EXPORT_PROPS[".png"])
        self.assertEqual(export_props[".svg"], OPTIONAL_FIGURE_EXPORT_PROPS[".svg"])

    def test_savefig_writes_pdf_by_default(self) -> None:
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])

        with tempfile.TemporaryDirectory() as tmp_dir:
            saved_paths = savefig(fig, Path(tmp_dir), "demo")

            self.assertEqual(len(saved_paths), 1)
            self.assertEqual(saved_paths[0].suffix, ".pdf")
            self.assertTrue(saved_paths[0].exists())
            self.assertEqual(saved_paths[0].parent.name, Path(tmp_dir).name)
            self.assertEqual(saved_paths[0].name, "demo.pdf")

        plt.close(fig)

    def test_savefig_writes_png_and_svg_in_subdirectories(self) -> None:
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])

        export_props = build_figure_export_props(
            include_pdf=True, include_png=True, include_svg=True
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            saved_paths = savefig(fig, output_dir, "demo", export_props=export_props)

            self.assertEqual(len(saved_paths), 3)

            pdf_path, png_path, svg_path = saved_paths
            self.assertEqual(pdf_path, output_dir / "demo.pdf")
            self.assertEqual(png_path, output_dir / "png-files" / "demo.png")
            self.assertEqual(svg_path, output_dir / "svg-files" / "demo.svg")

            for path in saved_paths:
                self.assertTrue(path.exists())

    def test_savefig_only_png(self) -> None:
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])

        export_props = build_figure_export_props(include_pdf=False, include_png=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            saved_paths = savefig(fig, output_dir, "demo", export_props=export_props)

            self.assertEqual(len(saved_paths), 1)
            self.assertEqual(saved_paths[0], output_dir / "png-files" / "demo.png")
            self.assertTrue(saved_paths[0].exists())
            # PDF should not have been written.
            self.assertFalse((output_dir / "demo.pdf").exists())

    def test_savefig_close_false_keeps_figure_open(self) -> None:
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])

        with tempfile.TemporaryDirectory() as tmp_dir:
            savefig(fig, Path(tmp_dir), "demo", close=False)

        # Figure should still be open (number remains tracked by pyplot).
        self.assertIn(fig.number, plt.get_fignums())
        plt.close(fig)


class TestBuildFigureExportProps(unittest.TestCase):
    def test_no_formats_returns_empty_mapping(self) -> None:
        export_props = build_figure_export_props(include_pdf=False)

        self.assertEqual(export_props, {})

    def test_png_only(self) -> None:
        export_props = build_figure_export_props(include_pdf=False, include_png=True)

        self.assertEqual(list(export_props.keys()), [".png"])


class TestSaveTable(unittest.TestCase):
    def setUp(self) -> None:
        self.df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})

    def test_default_export_is_csv_only(self) -> None:
        self.assertEqual(list(DEFAULT_TABLE_EXPORT_PROPS.keys()), [".csv"])

    def test_save_table_writes_csv_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            saved_paths = save_table(self.df, output_dir, "data")

            self.assertEqual(saved_paths, [output_dir / "data.csv"])
            self.assertTrue(saved_paths[0].exists())

    def test_save_table_writes_xlsx_in_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            saved_paths = save_table(self.df, output_dir, "data", export_props={".xlsx": {}})

            self.assertEqual(saved_paths, [output_dir / "xlsx-files" / "data.xlsx"])
            self.assertTrue(saved_paths[0].exists())

    def test_save_table_writes_parquet_in_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            saved_paths = save_table(self.df, output_dir, "data", export_props={".parquet": {}})

            self.assertEqual(saved_paths, [output_dir / "parquet-files" / "data.parquet"])
            self.assertTrue(saved_paths[0].exists())

    def test_save_table_skips_unsupported_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            saved_paths = save_table(self.df, output_dir, "data", export_props={".json": {}})

            self.assertEqual(saved_paths, [])

    def test_save_table_multiple_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            saved_paths = save_table(
                self.df,
                output_dir,
                "data",
                export_props={".csv": {}, ".xlsx": {}, ".unsupported": {}},
            )

            self.assertEqual(
                saved_paths,
                [output_dir / "data.csv", output_dir / "xlsx-files" / "data.xlsx"],
            )
