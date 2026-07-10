"""Read minimum pressure / water level from a cached case result.

Each optimization evaluation runs a scenario that caches time-series for the
surge-vessel water level and the keyword-matched pipe pressures (via the normal
extraction path). These helpers read the cached ``components`` DataFrame and
reduce it to the scalar metrics the acceptance criteria need.

The cached ``components`` DataFrame has a ``(component, property, s_location)``
MultiIndex on its columns and simulation time on its index; the minimum is taken
across *all* time steps and *all* spatial locations of the matching columns.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from ..postprocessing.io.cache import ParquetCache


def _min_for_property(components: pd.DataFrame, property_name: str) -> float:
    """Return the minimum value across all columns matching ``property_name``.

    Returns ``nan`` when the cache holds no matching column or only NaNs.
    """
    if components.empty or not isinstance(components.columns, pd.MultiIndex):
        return math.nan

    property_level = components.columns.get_level_values("property")
    mask = property_level == property_name
    if not mask.any():
        return math.nan

    selected = components.loc[:, mask]
    values = selected.to_numpy(dtype=float)
    if values.size == 0:
        return math.nan

    finite = values[~pd.isna(values)]
    if finite.size == 0:
        return math.nan
    return float(finite.min())


def read_min_metrics(
    case_dir: Path,
    pressure_property: str,
    water_level_property: str,
) -> tuple[float, float]:
    """Read ``(min_pressure, min_water_level)`` from a case's cached data.

    Args:
        case_dir: Case output directory containing the Parquet cache.
        pressure_property: Property name whose minimum is the pipeline pressure.
        water_level_property: Property name whose minimum is the vessel water level.

    Returns:
        Tuple ``(min_pressure, min_water_level)``; entries are ``nan`` when the
        corresponding property is absent from the cache.
    """
    components = ParquetCache(case_dir).read_components()
    min_pressure = _min_for_property(components, pressure_property)
    min_water_level = _min_for_property(components, water_level_property)
    return min_pressure, min_water_level
