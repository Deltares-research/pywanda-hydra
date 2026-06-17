"""Unit tests for wanda.session module."""

import unittest
from pathlib import Path

from pywandahydra.config.models import ModelSpecification
from pywandahydra.wanda.session import wanda_session

# Import shared helper from root conftest
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from conftest import find_wanda_bin


class TestWandaSession(unittest.TestCase):
    """Unit tests for wanda.session functions."""

    def setUp(self) -> None:
        """Set up a Wanda model for testing."""
        try:
            wanda_bin = find_wanda_bin()
        except FileNotFoundError as exc:
            self.skipTest(f"WANDA not available: {exc}")
        self.model_spec = ModelSpecification(
            model_path=Path(__file__).parents[2] / "data" / "wanda" / "base_model.wdi",
            wanda_bin=wanda_bin,
            base_model_name="base_model",
            run_steady=False,
            run_unsteady=False,
            readonly=False,
        )

    def test_wanda_session_context_manager(self):
        """Test the wanda_session context manager."""
        # Arrange & Act
        with wanda_session(spec=self.model_spec) as model:
            # Assert
            self.assertIsNotNone(model)
            self.assertEqual(len(model.get_all_components()), 24)
            self.assertEqual(len(model.get_all_pipes()), 3)

        # Assert closing the session
        with self.assertRaises(Exception):  # noqa: B017
            model.get_model_name()

    def test_wanda_session_with_upgrade_enabled(self):
        """Test the wanda_session context manager with upgrade=True."""
        # Arrange
        spec = self.model_spec.model_copy(update={"upgrade": True})

        # Act
        with wanda_session(spec=spec) as model:
            # Assert
            self.assertIsNotNone(model)
            self.assertEqual(len(model.get_all_pipes()), 3)

    def test_wanda_session_raises_for_invalid_wanda_bin(self):
        """Test that an invalid wanda_bin directory raises an exception."""
        # Arrange
        spec = self.model_spec.model_copy(update={"wanda_bin": Path(r"C:\does\not\exist")})

        # Act & Assert
        with self.assertRaises(Exception):  # noqa: B017
            with wanda_session(spec=spec):
                pass
