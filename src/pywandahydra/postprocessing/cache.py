"""Parquet-based extraction cache for per-case intermediate data.

Persists extracted DataFrames to Parquet files in the case directory so
that post-processing (plotting, tables) can run independently of the
WANDA model session.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class ParquetCache:
    """Read/write per-case extracted data as Parquet files.

    File layout in case_dir/data/::

        components.parquet   — time-series for component outputs
        routes/              — one parquet per route plot (keyed by spec title)
            <route_title>.parquet

    Args:
        case_dir: Path to the case directory.
    """

    def __init__(self, case_dir: Path) -> None:
        self.data_dir = case_dir

    def write(self, extracted: dict[str, Any]) -> dict[str, str]:
        """Persist extracted data to Parquet files.

        Args:
            extracted: Dict with keys "components" (DataFrame) and
                "routes" (dict[str, DataFrame]).

        Returns:
            Dict mapping artefact name → relative path (for journal).
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        artefacts: dict[str, str] = {}

        # Component outputs
        components_df: pd.DataFrame = extracted.get("components", pd.DataFrame())
        if not components_df.empty:
            path = self.data_dir / "components.parquet"
            # Flatten MultiIndex columns for Parquet compatibility
            if isinstance(components_df.columns, pd.MultiIndex):
                components_df = components_df.copy()
                components_df.columns = [f"{c[0]}|{c[1]}" for c in components_df.columns]
            components_df.to_parquet(path, engine="pyarrow")
            artefacts["components"] = str(path.relative_to(self.data_dir.parent))
            logger.info("Cached component outputs: %s", path)

        # Route outputs
        routes: dict[str, pd.DataFrame] = extracted.get("routes", {})
        if routes:
            routes_dir = self.data_dir / "routes"
            routes_dir.mkdir(parents=True, exist_ok=True)
            for title, route_df in routes.items():
                if route_df.empty:
                    continue
                safe_name = _sanitize_filename(title or "unnamed")
                path = routes_dir / f"{safe_name}.parquet"
                # Flatten MultiIndex columns
                if isinstance(route_df.columns, pd.MultiIndex):
                    route_df = route_df.copy()
                    route_df.columns = [f"{c[0]}|{c[1]}" for c in route_df.columns]
                route_df.to_parquet(path, engine="pyarrow")
                artefacts[f"route_{safe_name}"] = str(path.relative_to(self.data_dir.parent))
            logger.info("Cached %d route outputs", len(routes))

        return artefacts

    def read_components(self) -> pd.DataFrame:
        """Read cached component outputs.

        Returns:
            DataFrame with component time-series data, or empty DataFrame.
        """
        path = self.data_dir / "components.parquet"
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_parquet(path, engine="pyarrow")
        # Restore MultiIndex columns from "comp|prop" format
        if df.columns.nlevels == 1 and any("|" in str(c) for c in df.columns):
            tuples = [tuple(str(c).split("|", 1)) for c in df.columns]
            df.columns = pd.MultiIndex.from_tuples(tuples, names=["component", "property"])
        return df

    def read_route(self, title: str) -> pd.DataFrame:
        """Read a cached route output by title.

        Args:
            title: The route plot title (used as filename).

        Returns:
            DataFrame with route data, or empty DataFrame.
        """
        safe_name = _sanitize_filename(title)
        path = self.data_dir / "routes" / f"{safe_name}.parquet"
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_parquet(path, engine="pyarrow")
        # Restore MultiIndex columns
        if df.columns.nlevels == 1 and any("|" in str(c) for c in df.columns):
            tuples = [tuple(str(c).split("|", 1)) for c in df.columns]
            df.columns = pd.MultiIndex.from_tuples(tuples, names=["component", "property"])
        return df

    def list_routes(self) -> list[str]:
        """List available cached route titles.

        Returns:
            List of route titles (filenames without extension).
        """
        routes_dir = self.data_dir / "routes"
        if not routes_dir.exists():
            return []
        return [p.stem for p in routes_dir.glob("*.parquet")]

    def exists(self) -> bool:
        """Check if any cached data exists.

        Returns:
            True if the data directory contains at least one parquet file.
        """
        if not self.data_dir.exists():
            return False
        return any(self.data_dir.rglob("*.parquet"))


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename.

    Args:
        name: The raw string.

    Returns:
        Filesystem-safe string.
    """
    # Replace problematic characters
    safe = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
    safe = "".join(c for c in safe if c.isalnum() or c in ("_", "-", "."))
    return safe[:200] or "unnamed"
