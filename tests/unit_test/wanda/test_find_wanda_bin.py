"""Unit test for finding the Wanda binary."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pywandahydra.wanda.locate import WANDA_BIN_ENV_VAR, find_wanda_bin


class TestFindWandaBin(unittest.TestCase):
    """Unit tests for finding the Wanda binary."""

    def test_find_wanda_bin_via_env_var(self):
        """Test finding the Wanda binary via the environment variable."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Arrange
            wanda_bin_path = Path(tmp_dir)
            (wanda_bin_path / "Wandadef.dat").touch()

            with mock.patch.dict(
                "os.environ", {WANDA_BIN_ENV_VAR: str(wanda_bin_path)}
            ):
                # Act
                wanda_bin = find_wanda_bin()

            # Assert
            self.assertEqual(wanda_bin, wanda_bin_path)

    def test_find_wanda_bin_via_search_roots(self):
        """Test finding the Wanda binary by searching the default install roots."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Arrange
            root = Path(tmp_dir)
            install_dir = root / "Wanda 4.8"
            bin64_dir = install_dir / "Bin64"
            bin64_dir.mkdir(parents=True)
            (bin64_dir / "Wandadef.dat").touch()

            with (
                mock.patch.dict("os.environ", {}, clear=True),
                mock.patch("pywandahydra.wanda.locate._SEARCH_ROOTS", (root,)),
            ):
                # Act
                wanda_bin = find_wanda_bin()

            # Assert
            self.assertEqual(wanda_bin, bin64_dir)
