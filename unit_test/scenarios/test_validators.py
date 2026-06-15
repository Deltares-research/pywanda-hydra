"""Unit tests for scenario model normalization/validation helpers."""

from __future__ import annotations

import math
import unittest

from pywandahydra.scenarios.models.validators import (
    ensure_non_empty_string,
    normalize_fig,
    normalize_optional_float,
    normalize_optional_int,
)


class TestEnsureNonEmptyString(unittest.TestCase):
    def test_strips_and_returns_value(self) -> None:
        # Act
        result = ensure_non_empty_string("  hello  ")

        # Assert
        self.assertEqual(result, "hello")

    def test_non_string_value_is_stringified(self) -> None:
        # Act
        result = ensure_non_empty_string(42)

        # Assert
        self.assertEqual(result, "42")

    def test_empty_string_raises(self) -> None:
        # Act & Assert
        with self.assertRaises(ValueError) as ctx:
            ensure_non_empty_string("   ", field_name="route_id")

        self.assertIn("route_id", str(ctx.exception))

    def test_default_field_name_in_message(self) -> None:
        # Act & Assert
        with self.assertRaises(ValueError) as ctx:
            ensure_non_empty_string("")

        self.assertIn("value", str(ctx.exception))


class TestNormalizeFig(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(normalize_fig(None))

    def test_nan_float_returns_none(self) -> None:
        self.assertIsNone(normalize_fig(float("nan")))

    def test_integer_valued_float_returns_int_string(self) -> None:
        self.assertEqual(normalize_fig(3.0), "3")

    def test_non_integer_float_returns_str(self) -> None:
        self.assertEqual(normalize_fig(3.5), "3.5")

    def test_string_is_stripped(self) -> None:
        self.assertEqual(normalize_fig("  a  "), "a")

    def test_blank_string_returns_none(self) -> None:
        self.assertIsNone(normalize_fig("   "))


class TestNormalizeOptionalInt(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(normalize_optional_int(None, field_name="plot"))

    def test_nan_float_returns_none(self) -> None:
        self.assertIsNone(normalize_optional_int(float("nan"), field_name="plot"))

    def test_integer_valued_float_returns_int(self) -> None:
        self.assertEqual(normalize_optional_int(3.0, field_name="plot"), 3)

    def test_non_integer_float_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            normalize_optional_int(3.5, field_name="plot")

        self.assertIn("plot", str(ctx.exception))

    def test_digit_string_returns_int(self) -> None:
        self.assertEqual(normalize_optional_int("7", field_name="plot"), 7)

    def test_blank_string_returns_none(self) -> None:
        self.assertIsNone(normalize_optional_int("   ", field_name="plot"))

    def test_non_digit_string_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            normalize_optional_int("abc", field_name="plot")

        self.assertIn("plot", str(ctx.exception))

    def test_int_passthrough(self) -> None:
        self.assertEqual(normalize_optional_int(5, field_name="plot"), 5)

    def test_unsupported_type_returns_none(self) -> None:
        self.assertIsNone(normalize_optional_int([1, 2], field_name="plot"))


class TestNormalizeOptionalFloat(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(normalize_optional_float(None, field_name="location"))

    def test_nan_float_returns_none(self) -> None:
        self.assertIsNone(
            normalize_optional_float(float("nan"), field_name="location")
        )

    def test_float_passthrough(self) -> None:
        self.assertEqual(normalize_optional_float(1.5, field_name="location"), 1.5)

    def test_int_returns_float(self) -> None:
        result = normalize_optional_float(2, field_name="location")
        self.assertEqual(result, 2.0)
        self.assertIsInstance(result, float)

    def test_blank_string_returns_none(self) -> None:
        self.assertIsNone(normalize_optional_float("  ", field_name="location"))

    def test_numeric_string_returns_float(self) -> None:
        self.assertEqual(normalize_optional_float("1.25", field_name="location"), 1.25)

    def test_non_numeric_string_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            normalize_optional_float("abc", field_name="location")

        self.assertIn("location", str(ctx.exception))

    def test_unsupported_type_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            normalize_optional_float([1, 2], field_name="location")

        self.assertIn("location", str(ctx.exception))

    def test_result_is_finite(self) -> None:
        result = normalize_optional_float("1.0", field_name="location")
        self.assertTrue(math.isfinite(result))


if __name__ == "__main__":
    unittest.main()
