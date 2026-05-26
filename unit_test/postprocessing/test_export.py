"""Unit tests for postprocessing export helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

from pywandahydra.postprocessing.export import (  # noqa: E402
    DEFAULT_FIGURE_EXPORT_PROPS,
    OPTIONAL_FIGURE_EXPORT_PROPS,
    build_figure_export_props,
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
