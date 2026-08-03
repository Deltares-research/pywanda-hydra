from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from pywandahydra.results import (
    ComponentTimeSeries,
    ExtractedSimulationData,
    ParquetResultStore,
    RouteData,
    RouteIdentity,
)


def _data() -> ExtractedSimulationData:
    columns = pd.MultiIndex.from_tuples(
        [("Pump A", "Head", float("nan")), ("Pipe A", "Pressure", 12.5)],
        names=["component", "property", "s_location"],
    )
    components = pd.DataFrame(
        [[1.0, 2.0], [3.0, 4.0]],
        index=pd.Index([0.0, 1.0], name="time [s]"),
        columns=columns,
    )
    route = RouteIdentity("route-001", "Pressure")
    return ExtractedSimulationData(
        components=ComponentTimeSeries(components),
        routes={
            route: RouteData(
                timeseries=pd.DataFrame(
                    [[2.0, 3.0]],
                    index=pd.Index([0.0], name="time [s]"),
                    columns=pd.Index([0.0, 10.0], name="s_location [m]"),
                ),
                envelope=pd.DataFrame(
                    {"min": [1.0, 2.0], "max": [3.0, 4.0]},
                    index=pd.Index([0.0, 10.0], name="s_location [m]"),
                ),
                profile=pd.DataFrame(
                    {"elevation": [0.2, 0.5]},
                    index=pd.Index([0.0, 10.0], name="s_location [m]"),
                ),
            )
        },
    )


def test_roundtrip_preserves_multiindex_and_numeric_locations(tmp_path: Path) -> None:
    store = ParquetResultStore(tmp_path / "results")
    store.write(_data(), fingerprint="fingerprint")

    restored = store.read()

    assert restored is not None
    assert restored.components.data.columns.equals(_data().components.data.columns)
    assert restored.components.data.index.equals(_data().components.data.index)
    route = restored.routes[RouteIdentity("route-001", "Pressure")]
    assert route.timeseries is not None
    assert list(route.timeseries.columns.astype(float)) == [0.0, 10.0]
    assert route.envelope is not None
    assert list(route.envelope.index.astype(float)) == [0.0, 10.0]


def test_empty_data_roundtrip(tmp_path: Path) -> None:
    store = ParquetResultStore(tmp_path / "results")
    store.write(ExtractedSimulationData(), fingerprint="fingerprint")

    restored = store.read()

    assert restored is not None
    assert restored.components.data.empty
    assert restored.routes == {}


def test_payloads_are_owned_by_result_contracts() -> None:
    frame = pd.DataFrame({"value": [1.0]})
    components = ComponentTimeSeries(frame)
    frame.loc[0, "value"] = 2.0

    assert components.data.loc[0, "value"] == 1.0


def test_corrupt_or_missing_marker_never_reads_as_complete(tmp_path: Path) -> None:
    store = ParquetResultStore(tmp_path / "results")
    store.write(_data(), fingerprint="fingerprint")
    marker = tmp_path / "results" / "complete.json"

    marker.unlink()
    assert not store.is_complete()
    assert store.read() is None

    store.write(_data(), fingerprint="fingerprint")
    marker.write_text('{"metadata_sha256":"wrong"}', encoding="utf-8")
    assert not store.is_complete()


def test_corrupt_result_file_never_reads_as_complete(tmp_path: Path) -> None:
    store = ParquetResultStore(tmp_path / "results")
    store.write(_data(), fingerprint="fingerprint")
    (tmp_path / "results" / "components.parquet").write_bytes(b"corrupt")

    assert not store.is_complete()
    assert store.inventory() is None


def test_interrupted_write_without_completion_marker_is_incomplete(tmp_path: Path) -> None:
    store = ParquetResultStore(tmp_path / "results")
    store.write(_data(), fingerprint="fingerprint")
    (tmp_path / "results" / "complete.json").unlink()

    assert store.read() is None


def test_metadata_is_deterministic_and_uses_stable_route_identity(tmp_path: Path) -> None:
    data = _data()
    first = ParquetResultStore(tmp_path / "first")
    second = ParquetResultStore(tmp_path / "second")
    first.write(data, fingerprint="fingerprint")
    second.write(data, fingerprint="fingerprint")

    first_metadata = json.loads(
        (tmp_path / "first" / "inventory.json").read_text(encoding="utf-8")
    )
    second_metadata = json.loads(
        (tmp_path / "second" / "inventory.json").read_text(encoding="utf-8")
    )

    assert first_metadata == second_metadata
    assert "title" not in json.dumps(first_metadata)
    assert first_metadata["routes"][0]["route_id"] == "route-001"


def test_results_package_does_not_import_forbidden_runtime_dependencies() -> None:
    import pywandahydra.results  # noqa: F401

    forbidden = {"pywanda", "matplotlib", "pywandahydra.execution", "pywandahydra.postprocessing"}
    assert not forbidden.intersection(sys.modules)
