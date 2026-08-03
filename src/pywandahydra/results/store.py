"""Transactional Parquet persistence for extracted simulation results."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pandas as pd

from .models import (
    ComponentIdentity,
    ComponentTimeSeries,
    ExtractedSimulationData,
    RouteData,
    RouteIdentity,
    RouteProductIdentity,
)
from .requirements import ResultInventory

_MARKER_FILE = "complete.json"
_METADATA_FILE = "inventory.json"
_COMPONENTS_FILE = "components.parquet"
_ROUTES_DIRECTORY = "routes"
_SCHEMA_VERSION = 1


class ParquetResultStore:
    """Read and atomically commit one case's WANDA-free extracted data."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def is_complete(self) -> bool:
        """Return whether a valid completion marker and all hashed files exist."""
        marker_path = self.directory / _MARKER_FILE
        metadata_path = self.directory / _METADATA_FILE
        if not marker_path.is_file() or not metadata_path.is_file():
            return False
        try:
            marker = _read_json(marker_path)
            if marker.get("metadata_sha256") != _sha256(metadata_path):
                return False
            metadata = _read_json(metadata_path)
            return all(
                (self.directory / relative_path).is_file()
                and _sha256(self.directory / relative_path) == expected_hash
                for relative_path, expected_hash in metadata["files"].items()
            )
        except (KeyError, OSError, ValueError, json.JSONDecodeError):
            return False

    def inventory(self) -> ResultInventory | None:
        """Return the committed inventory, or ``None`` for incomplete stores."""
        if not self.is_complete():
            return None
        return _inventory_from_json(_read_json(self.directory / _METADATA_FILE)["inventory"])

    def read(self) -> ExtractedSimulationData | None:
        """Read committed result data, or ``None`` for incomplete stores."""
        if not self.is_complete():
            return None
        metadata = _read_json(self.directory / _METADATA_FILE)
        files: dict[str, str] = metadata["files"]
        components_path = self.directory / _COMPONENTS_FILE
        components = ComponentTimeSeries(
            _read_components(components_path) if _COMPONENTS_FILE in files else pd.DataFrame()
        )
        routes: dict[RouteIdentity, RouteData] = {}
        for item in metadata["routes"]:
            identity = RouteIdentity(item["route_id"], item["property"])
            values: dict[str, pd.DataFrame] = {}
            for product, relative_path in item["products"].items():
                values[product] = pd.read_parquet(self.directory / relative_path, engine="pyarrow")
            routes[identity] = RouteData(**values)
        return ExtractedSimulationData(components=components, routes=routes)

    def write(self, data: ExtractedSimulationData, *, fingerprint: str) -> ResultInventory:
        """Atomically commit ``data`` and its inventory after all Parquet writes close."""
        self.directory.mkdir(parents=True, exist_ok=True)
        marker_path = self.directory / _MARKER_FILE
        marker_path.unlink(missing_ok=True)

        files: dict[str, str] = {}
        if not data.components.data.empty:
            files[_COMPONENTS_FILE] = self._write_dataframe(
                _COMPONENTS_FILE, _encode_component_columns(data.components.data)
            )

        routes_json: list[dict[str, Any]] = []
        for identity, route_data in sorted(data.routes.items()):
            products: dict[str, str] = {}
            route_directory = _route_directory(identity)
            for product in route_data.products():
                relative_path = f"{_ROUTES_DIRECTORY}/{route_directory}/{product}.parquet"
                frame = getattr(route_data, product)
                if frame is not None:
                    files[relative_path] = self._write_dataframe(relative_path, frame)
                    products[product] = relative_path
            routes_json.append(
                {"route_id": identity.route_id, "property": identity.property, "products": products}
            )

        inventory = ResultInventory.from_data(data)
        metadata = {
            "schema_version": _SCHEMA_VERSION,
            "fingerprint": fingerprint,
            "inventory": _inventory_to_json(inventory),
            "files": dict(sorted(files.items())),
            "routes": routes_json,
        }
        metadata_path = self.directory / _METADATA_FILE
        _atomic_json_write(metadata_path, metadata)
        _atomic_json_write(marker_path, {"metadata_sha256": _sha256(metadata_path)})
        return inventory

    def _write_dataframe(self, relative_path: str, data: pd.DataFrame) -> str:
        path = self.directory / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        data.to_parquet(temporary_path, engine="pyarrow")
        os.replace(temporary_path, path)
        return _sha256(path)


def _route_directory(identity: RouteIdentity) -> str:
    encoded = json.dumps([identity.route_id, identity.property], separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return value


def _atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        json.dump(value, temporary, sort_keys=True, separators=(",", ":"))
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def _encode_component_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Encode component MultiIndex columns without relying on PyArrow metadata."""
    if not isinstance(data.columns, pd.MultiIndex) or data.columns.nlevels != 3:
        return data
    encoded = data.copy(deep=True)
    encoded.columns = pd.Index(
        [
            json.dumps(
                [
                    str(component),
                    str(property_name),
                    None if pd.isna(location) else float(location),
                ],
                separators=(",", ":"),
            )
            for component, property_name, location in data.columns
        ]
    )
    return encoded


def _read_components(path: Path) -> pd.DataFrame:
    """Restore typed component MultiIndex columns from explicit JSON encodings."""
    data = pd.read_parquet(path, engine="pyarrow")
    if not all(isinstance(column, str) for column in data.columns):
        return data
    try:
        columns = [tuple(json.loads(column)) for column in data.columns]
    except (TypeError, json.JSONDecodeError):
        return data
    if not all(len(column) == 3 for column in columns):
        return data
    restored = data.copy(deep=True)
    restored.columns = pd.MultiIndex.from_tuples(
        columns, names=["component", "property", "s_location"]
    )
    return restored


def _inventory_to_json(inventory: ResultInventory) -> dict[str, list[dict[str, Any]]]:
    return {
        "components": [
            {"component": item.component, "property": item.property, "location": item.location}
            for item in sorted(inventory.components)
        ],
        "route_products": [
            {
                "route_id": item.route.route_id,
                "property": item.route.property,
                "product": item.product,
            }
            for item in sorted(inventory.route_products)
        ],
    }


def _inventory_from_json(value: dict[str, Any]) -> ResultInventory:
    return ResultInventory(
        components=frozenset(
            ComponentIdentity(item["component"], item["property"], item["location"])
            for item in value["components"]
        ),
        route_products=frozenset(
            RouteProductIdentity(RouteIdentity(item["route_id"], item["property"]), item["product"])
            for item in value["route_products"]
        ),
    )
