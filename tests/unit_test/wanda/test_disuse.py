"""Unit tests for legacy disuse parsing semantics."""

import unittest

from pywandahydra.disuse import parse_disuse_value
from pywandahydra.scenarios import ModelParameterChange


class TestDisuseSemantics(unittest.TestCase):
    """Validate legacy disuse semantics from parameter_wanda."""

    def test_parse_disuse_true_tokens(self) -> None:
        for raw in (0, 0.0, "0", "yes", "true", "y", "disuse"):
            self.assertTrue(parse_disuse_value(raw), msg=f"Expected disused for {raw!r}")

    def test_parse_disuse_false_tokens(self) -> None:
        for raw in (1, 1.0, "1", "no", "false", "n", "use"):
            self.assertFalse(parse_disuse_value(raw), msg=f"Expected in-use for {raw!r}")

    def test_parameter_change_stores_raw_disuse_value(self) -> None:
        disused = ModelParameterChange(component="P1", property="disuse", value=0)
        in_use = ModelParameterChange(component="P1", property="disuse", value=1)
        self.assertEqual(disused.value, 0)
        self.assertEqual(in_use.value, 1)

    def test_invalid_disuse_value_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_disuse_value("maybe")

