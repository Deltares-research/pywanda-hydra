from __future__ import annotations

import pandas as pd
import pytest

from pywandahydra.postprocessing.io.cache import ParquetCache, _sanitize_filename


def test_route_profile_roundtrip(parquet_cache: ParquetCache) -> None:
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

    parquet_cache.write(extracted)
    route = parquet_cache.read_route("Route A")

    assert "profile" in route
    profile = route["profile"]
    assert "elevation" in profile.columns
    assert list(profile.index.astype(float)) == [0.0, 5.0, 10.0]
    assert list(profile["elevation"].astype(float)) == [0.5, 0.25, 0.75]


def test_components_roundtrip_with_multiindex_columns(parquet_cache: ParquetCache) -> None:
    columns = pd.MultiIndex.from_tuples(
        [("PUMP P1", "Head", float("nan")), ("PIPE P1", "Pressure", 10.0)],
        names=["component", "property", "s_location"],
    )
    components = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], columns=columns, index=[0.0, 1.0])

    artefacts = parquet_cache.write({"components": components, "routes": {}})

    assert "components" in artefacts
    assert (parquet_cache.data_dir / "components.parquet").exists()

    restored = parquet_cache.read_components()

    assert restored.columns.nlevels == 3
    assert restored.columns[0][:2] == ("PUMP P1", "Head")
    assert pd.isna(restored.columns[0][2])
    assert restored.columns[1] == ("PIPE P1", "Pressure", 10.0)


def test_read_components_without_cache_returns_empty(parquet_cache: ParquetCache) -> None:
    result = parquet_cache.read_components()

    assert result.empty


def test_exists_false_when_no_data_written(parquet_cache: ParquetCache) -> None:
    assert not parquet_cache.exists()


def test_exists_true_after_write(parquet_cache: ParquetCache) -> None:
    components = pd.DataFrame({"a": [1.0]})

    parquet_cache.write({"components": components, "routes": {}})

    assert parquet_cache.exists()


def test_list_routes_returns_sorted_titles(parquet_cache: ParquetCache) -> None:
    envelope = pd.DataFrame(
        {"min": [1.0], "max": [2.0]},
        index=pd.Index([0.0], name="s_location [m]"),
    )

    parquet_cache.write(
        {
            "components": pd.DataFrame(),
            "routes": {
                "Route B": {"envelope": envelope},
                "Route A": {"envelope": envelope},
            },
        }
    )

    assert parquet_cache.list_routes() == ["Route_A", "Route_B"]


def test_read_route_for_missing_title_returns_empty_dict(parquet_cache: ParquetCache) -> None:
    result = parquet_cache.read_route("does not exist")

    assert result == {}


def test_write_skips_non_dict_route_payload(parquet_cache: ParquetCache) -> None:
    artefacts = parquet_cache.write(
        {"components": pd.DataFrame(), "routes": {"Bad Route": "not-a-dict"}}
    )

    assert artefacts == {}
    assert parquet_cache.list_routes() == []


def test_write_and_read_simple_custom_dataframe(parquet_cache: ParquetCache) -> None:
    df = pd.DataFrame({"value": [1, 2, 3]})

    artefacts = parquet_cache.write_custom({"my_extractor": df})

    assert "custom_my_extractor" in artefacts
    result = parquet_cache.read_custom("my_extractor")
    assert list(result["value"]) == [1, 2, 3]


def test_write_and_read_nested_custom_extraction(parquet_cache: ParquetCache) -> None:
    nested = {
        "timeseries": pd.DataFrame({"value": [1.0, 2.0]}),
        "profile": pd.DataFrame({"elevation": [0.0, 1.0]}),
    }

    artefacts = parquet_cache.write_custom({"my_extractor": nested})

    assert "custom_my_extractor_timeseries" in artefacts
    assert "custom_my_extractor_profile" in artefacts

    result = parquet_cache.read_custom("my_extractor")
    assert isinstance(result, dict)
    assert list(result["timeseries"]["value"]) == [1.0, 2.0]


def test_write_custom_skips_empty_dataframe(parquet_cache: ParquetCache) -> None:
    artefacts = parquet_cache.write_custom({"empty": pd.DataFrame()})

    assert artefacts == {}


def test_write_custom_skips_unsupported_type(parquet_cache: ParquetCache) -> None:
    artefacts = parquet_cache.write_custom({"bad": object()})

    assert artefacts == {}


def test_write_custom_with_empty_dict_returns_empty(parquet_cache: ParquetCache) -> None:
    assert parquet_cache.write_custom({}) == {}


def test_read_custom_without_cache_returns_empty_dataframe(parquet_cache: ParquetCache) -> None:
    result = parquet_cache.read_custom("nothing")

    assert isinstance(result, pd.DataFrame)
    assert result.empty  # type: ignore[union-attr]


def test_list_custom_extractors(parquet_cache: ParquetCache) -> None:
    parquet_cache.write_custom(
        {
            "simple": pd.DataFrame({"a": [1]}),
            "nested": {"part": pd.DataFrame({"b": [2]})},
        }
    )

    assert parquet_cache.list_custom_extractors() == ["nested", "simple"]


def test_sanitize_filename_replaces_path_separators_and_spaces() -> None:
    assert _sanitize_filename("a/b\\c d") == "a_b_c_d"


def test_sanitize_filename_strips_unsupported_characters() -> None:
    assert _sanitize_filename("Route #1 (main)!") == "Route_1_main"


def test_sanitize_filename_empty_string_returns_unnamed() -> None:
    assert _sanitize_filename("") == "unnamed"


def test_sanitize_filename_truncates_to_200_characters() -> None:
    long_name = "a" * 300

    assert len(_sanitize_filename(long_name)) == 200
