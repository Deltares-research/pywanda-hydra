from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pywandahydra.postprocessing.io.cache import ParquetCache, _sanitize_filename


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
            self.assertListEqual(list(profile["elevation"].astype(float)), [0.5, 0.25, 0.75])


class TestParquetCacheComponents(unittest.TestCase):
    def test_components_roundtrip_with_multiindex_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))

            columns = pd.MultiIndex.from_tuples(
                [("PUMP P1", "Head", float("nan")), ("PIPE P1", "Pressure", 10.0)],
                names=["component", "property", "s_location"],
            )
            components = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], columns=columns, index=[0.0, 1.0])

            artefacts = cache.write({"components": components, "routes": {}})

            self.assertIn("components", artefacts)
            self.assertTrue((Path(tmp_dir) / "components.parquet").exists())

            restored = cache.read_components()

            self.assertEqual(restored.columns.nlevels, 3)
            self.assertEqual(restored.columns[0][:2], ("PUMP P1", "Head"))
            self.assertTrue(pd.isna(restored.columns[0][2]))
            self.assertEqual(restored.columns[1], ("PIPE P1", "Pressure", 10.0))

    def test_read_components_without_cache_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))

            result = cache.read_components()

            self.assertTrue(result.empty)


class TestParquetCacheExistsAndListRoutes(unittest.TestCase):
    def test_exists_false_when_no_data_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))

            self.assertFalse(cache.exists())

    def test_exists_true_after_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))
            components = pd.DataFrame({"a": [1.0]})

            cache.write({"components": components, "routes": {}})

            self.assertTrue(cache.exists())

    def test_list_routes_returns_sorted_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))
            envelope = pd.DataFrame(
                {"min": [1.0], "max": [2.0]},
                index=pd.Index([0.0], name="s_location [m]"),
            )

            cache.write(
                {
                    "components": pd.DataFrame(),
                    "routes": {
                        "Route B": {"envelope": envelope},
                        "Route A": {"envelope": envelope},
                    },
                }
            )

            self.assertEqual(cache.list_routes(), ["Route_A", "Route_B"])

    def test_read_route_for_missing_title_returns_empty_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))

            result = cache.read_route("does not exist")

            self.assertEqual(result, {})

    def test_write_skips_non_dict_route_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))

            artefacts = cache.write(
                {"components": pd.DataFrame(), "routes": {"Bad Route": "not-a-dict"}}
            )

            self.assertEqual(artefacts, {})
            self.assertEqual(cache.list_routes(), [])


class TestParquetCacheCustomExtractions(unittest.TestCase):
    def test_write_and_read_simple_custom_dataframe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))
            df = pd.DataFrame({"value": [1, 2, 3]})

            artefacts = cache.write_custom({"my_extractor": df})

            self.assertIn("custom_my_extractor", artefacts)
            result = cache.read_custom("my_extractor")
            self.assertListEqual(list(result["value"]), [1, 2, 3])

    def test_write_and_read_nested_custom_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))
            nested = {
                "timeseries": pd.DataFrame({"value": [1.0, 2.0]}),
                "profile": pd.DataFrame({"elevation": [0.0, 1.0]}),
            }

            artefacts = cache.write_custom({"my_extractor": nested})

            self.assertIn("custom_my_extractor_timeseries", artefacts)
            self.assertIn("custom_my_extractor_profile", artefacts)

            result = cache.read_custom("my_extractor")
            self.assertIsInstance(result, dict)
            self.assertListEqual(list(result["timeseries"]["value"]), [1.0, 2.0])

    def test_write_custom_skips_empty_dataframe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))

            artefacts = cache.write_custom({"empty": pd.DataFrame()})

            self.assertEqual(artefacts, {})

    def test_write_custom_skips_unsupported_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))

            artefacts = cache.write_custom({"bad": object()})

            self.assertEqual(artefacts, {})

    def test_write_custom_with_empty_dict_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))

            self.assertEqual(cache.write_custom({}), {})

    def test_read_custom_without_cache_returns_empty_dataframe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))

            result = cache.read_custom("nothing")

            self.assertIsInstance(result, pd.DataFrame)
            self.assertTrue(result.empty)  # type: ignore[union-attr]

    def test_list_custom_extractors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ParquetCache(Path(tmp_dir))
            cache.write_custom(
                {
                    "simple": pd.DataFrame({"a": [1]}),
                    "nested": {"part": pd.DataFrame({"b": [2]})},
                }
            )

            self.assertEqual(cache.list_custom_extractors(), ["nested", "simple"])


class TestSanitizeFilename(unittest.TestCase):
    def test_replaces_path_separators_and_spaces(self) -> None:
        self.assertEqual(_sanitize_filename("a/b\\c d"), "a_b_c_d")

    def test_strips_unsupported_characters(self) -> None:
        self.assertEqual(_sanitize_filename("Route #1 (main)!"), "Route_1_main")

    def test_empty_string_returns_unnamed(self) -> None:
        self.assertEqual(_sanitize_filename(""), "unnamed")

    def test_truncates_to_200_characters(self) -> None:
        long_name = "a" * 300

        self.assertEqual(len(_sanitize_filename(long_name)), 200)
