"""Parquet-based extraction cache for per-case intermediate data.

Persists extracted DataFrames to Parquet files in the case directory so
that post-processing (plotting, tables) can run independently of the
WANDA model session.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_COMPONENT_COL_NAMES = ["component", "property", "s_location"]
_COL_SEP = "|"


class ParquetCache:
    """Read/write per-case extracted data as Parquet files.

    File layout in case_dir/data/::

        components.parquet           — time-series for component outputs
        routes/                      — one sub-directory per route plot
            <route_title>/
                timeseries.parquet   — time × s_location data
                envelope.parquet     — min/max envelope along s_location
                profile.parquet      — elevation profile along s_location

    Args:
        case_dir: Path to the case directory.
    """

    def __init__(self, case_dir: Path) -> None:
        self.data_dir = case_dir

    # -----------------------------------------------------------------
    # Write
    # -----------------------------------------------------------------
    def write(self, extracted: dict[str, Any]) -> dict[str, str]:
        """Persist extracted data to Parquet files.

        Args:
            extracted: Dict with keys ``"components"`` (DataFrame) and
                ``"routes"`` (``dict[title, {"timeseries": df,
                "envelope": df, "profile": df}]``).

        Returns:
            Dict mapping artefact name → relative path (for the journal).
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        artefacts: dict[str, str] = {}

        # --- Component outputs -------------------------------------------------
        components_df: pd.DataFrame = extracted.get("components", pd.DataFrame())
        if not components_df.empty:
            path = self.data_dir / "components.parquet"
            _write_with_flat_cols(components_df, path)
            artefacts["components"] = str(path.relative_to(self.data_dir.parent))
            logger.info("Cached component outputs: %s", path)

        # --- Route outputs -----------------------------------------------------
        routes: dict[str, dict[str, pd.DataFrame]] = extracted.get("routes", {})
        if routes:
            routes_dir = self.data_dir / "routes"
            routes_dir.mkdir(parents=True, exist_ok=True)
            for title, route_dict in routes.items():
                if not isinstance(route_dict, dict):
                    logger.warning(
                        "Route '%s' has unexpected payload type %s – skipping.",
                        title,
                        type(route_dict).__name__,
                    )
                    continue
                safe_name = _sanitize_filename(title or "unnamed")
                route_subdir = routes_dir / safe_name
                route_subdir.mkdir(parents=True, exist_ok=True)

                ts_df = route_dict.get("timeseries")
                if isinstance(ts_df, pd.DataFrame) and not ts_df.empty:
                    ts_path = route_subdir / "timeseries.parquet"
                    _write_with_flat_cols(ts_df, ts_path)
                    artefacts[f"route_{safe_name}_timeseries"] = str(
                        ts_path.relative_to(self.data_dir.parent)
                    )

                env_df = route_dict.get("envelope")
                if isinstance(env_df, pd.DataFrame) and not env_df.empty:
                    env_path = route_subdir / "envelope.parquet"
                    env_df.to_parquet(env_path, engine="pyarrow")
                    artefacts[f"route_{safe_name}_envelope"] = str(
                        env_path.relative_to(self.data_dir.parent)
                    )

                profile_df = route_dict.get("profile")
                if isinstance(profile_df, pd.DataFrame) and not profile_df.empty:
                    profile_path = route_subdir / "profile.parquet"
                    profile_df.to_parquet(profile_path, engine="pyarrow")
                    artefacts[f"route_{safe_name}_profile"] = str(
                        profile_path.relative_to(self.data_dir.parent)
                    )

            logger.info("Cached %d route outputs", len(routes))

        return artefacts

    # -----------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------
    def read_components(self) -> pd.DataFrame:
        """Read cached component outputs.

        Returns:
            DataFrame with the original ``(component, property,
            s_location)`` MultiIndex columns restored, or an empty
            DataFrame when no cache exists.
        """
        path = self.data_dir / "components.parquet"
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_parquet(path, engine="pyarrow")
        return _restore_flat_cols(df)

    def read_route(self, title: str) -> dict[str, pd.DataFrame]:
        """Read a cached route output by title.

        Args:
            title: The route plot title (used as filename stem).

        Returns:
            ``{"timeseries": df, "envelope": df, "profile": df}`` with whichever keys
            are available on disk. Empty dict if nothing is cached.
        """
        safe_name = _sanitize_filename(title)
        route_subdir = self.data_dir / "routes" / safe_name
        result: dict[str, pd.DataFrame] = {}

        ts_path = route_subdir / "timeseries.parquet"
        if ts_path.exists():
            result["timeseries"] = _restore_flat_cols(pd.read_parquet(ts_path, engine="pyarrow"))

        env_path = route_subdir / "envelope.parquet"
        if env_path.exists():
            env_df = pd.read_parquet(env_path, engine="pyarrow")
            # Index name was preserved via pyarrow; ensure it is set.
            if env_df.index.name is None:
                env_df.index.name = "s_location [m]"
            result["envelope"] = env_df

        profile_path = route_subdir / "profile.parquet"
        if profile_path.exists():
            profile_df = pd.read_parquet(profile_path, engine="pyarrow")
            if profile_df.index.name is None:
                profile_df.index.name = "s_location [m]"
            result["profile"] = profile_df

        return result

    def list_routes(self) -> list[str]:
        """List available cached route titles.

        Returns:
            Sorted list of route sub-directory names (sanitised titles).
        """
        routes_dir = self.data_dir / "routes"
        if not routes_dir.exists():
            return []
        return sorted(p.name for p in routes_dir.iterdir() if p.is_dir())

    def exists(self) -> bool:
        """Check if any cached data exists.

        Returns:
            True if the data directory contains at least one parquet file.
        """
        if not self.data_dir.exists():
            return False
        return any(self.data_dir.rglob("*.parquet"))

# ---------------------------------------------------------------------------
# Column (de)serialisation helpers
# ---------------------------------------------------------------------------


def _flatten_multiindex_columns(cols: pd.MultiIndex) -> list[str]:
    """Encode a MultiIndex as ``"lvl0|lvl1|..."`` strings.

    NaN levels are written as the empty string so they round-trip cleanly.
    """
    out: list[str] = []
    for tup in cols:
        parts: list[str] = []
        for v in tup:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                parts.append("")
            else:
                parts.append(str(v))
        out.append(_COL_SEP.join(parts))
    return out


def _write_with_flat_cols(df: pd.DataFrame, path: Path) -> None:
    """Flatten MultiIndex columns (if any) and write to Parquet."""
    if isinstance(df.columns, pd.MultiIndex):
        flat = _flatten_multiindex_columns(df.columns)
        df = df.copy()
        df.columns = pd.Index(flat)
    df.to_parquet(path, engine="pyarrow")


def _restore_flat_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Restore a ``(component, property, s_location)`` MultiIndex.

    Only acts on a flat string column index that uses ``|`` as separator.
    s_location is parsed back to ``float`` (empty → ``NaN``).
    """
    if df.columns.nlevels != 1:
        return df
    if not any(_COL_SEP in str(c) for c in df.columns):
        return df

    tuples: list[tuple[Any, ...]] = []
    for raw in df.columns:
        parts = str(raw).split(_COL_SEP)
        # Pad to 3 levels for backwards compatibility with 2-level caches.
        while len(parts) < len(_COMPONENT_COL_NAMES):
            parts.append("")
        component, prop, s_str = parts[0], parts[1], parts[2]
        try:
            s_val: float = float(s_str) if s_str != "" else float("nan")
        except ValueError:
            s_val = float("nan")
        tuples.append((component, prop, s_val))

    df = df.copy()
    df.columns = pd.MultiIndex.from_tuples(tuples, names=_COMPONENT_COL_NAMES)
    return df


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename.

    Args:
        name: The raw string.

    Returns:
        Filesystem-safe string.
    """
    safe = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
    safe = "".join(c for c in safe if c.isalnum() or c in ("_", "-", "."))
    return safe[:200] or "unnamed"
