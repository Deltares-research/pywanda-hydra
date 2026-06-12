from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pywandahydra.postprocessing.io.cache import ParquetCache


class TestParquetCacheRouteProfile(unittest.TestCase):
    def test_route_profile_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))

            extracted = {
                "components": pd.DataFrame(),
                "routes": {
                    "Route A": {
                        "envelope": pd.DataFrame(
                            {"min": [1.0, 2.0], "max": [3.0, 4.0]},
                            index=pd.Index([0.0, 10.0], name="s_location [m]"),
                        ),
                        "profile": pd.DataFrame(
                            {"elevation": [0.5, 0.25, 0.75]},
                            index=pd.Index([0.0, 5.0, 10.0], name="s_location [m]"),
                        ),
                    }
                },
            }

            cache.write(extracted)
            route = cache.read_route("Route A")

            self.assertIn("profile", route)
            profile = route["profile"]
            self.assertIn("elevation", profile.columns)
            self.assertListEqual(list(profile.index.astype(float)), [0.0, 5.0, 10.0])
            self.assertListEqual(
                list(profile["elevation"].astype(float)), [0.5, 0.25, 0.75]
            )
