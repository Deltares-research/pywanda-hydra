"""Unit tests for layout helpers in postprocessing plotting styles."""

from __future__ import annotations

import unittest
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # headless backend for CI / unit tests

import matplotlib.pyplot as plt
import numpy as np

from pywandahydra.postprocessing.plotting.styles.layout import (
    PageMetadata,
    _calculate_layout_coordinates,
    draw_layout,
    load_default_logo,
)


class TestLoadDefaultLogo(unittest.TestCase):
    def test_load_default_logo_returns_array(self) -> None:
        # Arrange / Act
        logo = load_default_logo()

        # Assert
        self.assertIsInstance(logo, np.ndarray)
        self.assertGreater(logo.ndim, 1)

    def test_load_default_logo_is_cached(self) -> None:
        # Arrange / Act
        logo1 = load_default_logo()
        logo2 = load_default_logo()

        # Assert
        self.assertIs(logo1, logo2)


class TestCalculateLayoutCoordinates(unittest.TestCase):
    def test_returns_two_tuples_of_four_floats(self) -> None:
        # Act
        vertical, horizontal = _calculate_layout_coordinates()

        # Assert
        self.assertEqual(len(vertical), 4)
        self.assertEqual(len(horizontal), 4)
        for value in vertical + horizontal:
            self.assertIsInstance(value, float)

    def test_coordinates_are_increasing(self) -> None:
        # Act
        vertical, horizontal = _calculate_layout_coordinates()

        # Assert
        self.assertTrue(vertical[0] < vertical[1] < vertical[2] < vertical[3])
        self.assertTrue(horizontal[0] < horizontal[1] < horizontal[2] < horizontal[3])


class TestPageMetadata(unittest.TestCase):
    def _base_kwargs(self) -> dict:
        return dict(
            title="My Title",
            case_title="Case Title",
            case_description="Case Description",
            proj_number="12345",
            section_name="Section A",
            fig_name="Figure 1",
        )

    def test_effective_date_defaults_to_today(self) -> None:
        # Arrange
        meta = PageMetadata(**self._base_kwargs())

        # Act
        effective_date = meta.effective_date

        # Assert
        self.assertIsInstance(effective_date, datetime)
        self.assertEqual(effective_date.date(), datetime.today().date())  # type: ignore[attr-defined]

    def test_effective_date_uses_provided_date(self) -> None:
        # Arrange
        fixed_date = datetime(2020, 1, 2)
        meta = PageMetadata(date=fixed_date, **self._base_kwargs())

        # Act / Assert
        self.assertEqual(meta.effective_date, fixed_date)

    def test_non_empty_str_validator_strips_whitespace(self) -> None:
        # Arrange
        kwargs = self._base_kwargs()
        kwargs["title"] = "  Padded Title  "

        # Act
        meta = PageMetadata(**kwargs)

        # Assert
        self.assertEqual(meta.title, "Padded Title")

    def test_non_empty_str_validator_rejects_blank_string(self) -> None:
        # Arrange
        kwargs = self._base_kwargs()
        kwargs["title"] = "   "

        # Act / Assert
        with self.assertRaises(ValueError):
            PageMetadata(**kwargs)

    def test_coerce_project_number_from_integer_float(self) -> None:
        # Arrange
        kwargs = self._base_kwargs()
        kwargs["proj_number"] = 123.0

        # Act / Assert
        # The "before" validator coerces an integer-valued float to int,
        # but the declared field type is str, so pydantic still raises.
        with self.assertRaises(ValueError):
            PageMetadata(**kwargs)

    def test_coerce_project_number_from_non_integer_float(self) -> None:
        # Arrange
        kwargs = self._base_kwargs()
        kwargs["proj_number"] = 123.5

        # Act
        meta = PageMetadata(**kwargs)

        # Assert
        self.assertEqual(meta.proj_number, "123.5")

    def test_coerce_project_number_from_string(self) -> None:
        # Arrange
        kwargs = self._base_kwargs()
        kwargs["proj_number"] = "P-001"

        # Act
        meta = PageMetadata(**kwargs)

        # Assert
        self.assertEqual(meta.proj_number, "P-001")


class TestDrawLayout(unittest.TestCase):
    def test_draw_layout_adds_axes_and_text(self) -> None:
        # Arrange
        meta = PageMetadata(
            title="Title",
            case_title="Case",
            case_description="Description",
            proj_number="42",
            section_name="Section",
            fig_name="Fig1",
            date=datetime(2021, 5, 17),
        )
        fig = plt.figure()

        # Act
        draw_layout(fig, meta)

        # Assert
        # - One axes for the lines/box, one for the watermark image
        self.assertEqual(len(fig.axes), 2)

        texts = [t.get_text() for t in fig.texts]
        self.assertIn("Section", texts)
        self.assertIn("42", texts)
        self.assertIn("Deltares", texts)
        self.assertIn("Fig1", texts)
        self.assertIn("WANDA 4.8", texts)
        self.assertIn("17-05-2021", texts)
        self.assertIn("Case\nDescription", texts)

        plt.close(fig)

    def test_draw_layout_with_custom_company_image(self) -> None:
        # Arrange
        # Note: company_image is combined via `meta.company_image or
        # _default_logo()`, so a multi-element numpy array would raise
        # (ambiguous truth value). Use a single-pixel array instead.
        custom_image = np.ones((1, 1, 1))
        meta = PageMetadata(
            title="Title",
            case_title="Case",
            case_description="Description",
            proj_number="1",
            section_name="Section",
            fig_name="Fig1",
            company_image=custom_image,
        )
        fig = plt.figure()

        # Act
        draw_layout(fig, meta)

        # Assert
        watermark_ax = fig.axes[-1]
        images = watermark_ax.get_images()
        self.assertEqual(len(images), 1)
        np.testing.assert_array_equal(np.asarray(images[0].get_array()), custom_image.squeeze(-1))

        plt.close(fig)


if __name__ == "__main__":
    unittest.main()
