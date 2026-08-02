"""Extract time-series and route data from simulated WANDA models.

This module provides routines that read the *outputs* and *route_plots*
specifications stored on a :class:`ScenarioSpecification` and extract
the corresponding data from an open ``pywanda.WandaModel`` into
multi-header :class:`~pandas.DataFrame` objects suitable for further
post-processing, plotting or export.

Typical usage::

    from pywandahydra.postprocessing.extract import (
        extract_component_outputs,
        extract_route_outputs,
        extract_all,
    )

    results = extract_all(model, scenario, adapter)
    # results["components"]  -> DataFrame with component time series
    # results["routes"]      -> dict[str, dict[str, DataFrame]] keyed by route title
    #                           inner keys: "timeseries" (time × s_location)
    #                                       "envelope"   (s_location × {min, max})
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
import pywanda

from ...scenarios.schema import (
    MinMaxTableSpecification,
    RoutePlotSpecification,
    ScenarioSpecification,
    TimeSeriesPlotSpecification,
)
from ...wanda.model_access import WandaModelAccess

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Component / keyword extraction  (Output sheet specifications)
# ---------------------------------------------------------------------------


def extract_component_outputs(
    model: pywanda.WandaModel,
    specs: Sequence[MinMaxTableSpecification | TimeSeriesPlotSpecification],
    adapter: WandaModelAccess,
) -> pd.DataFrame:
    """Extract time-series data for every *Output* specification.

    Each specification identifies a *component* (or keyword) and a
    *property*. The component identifier is resolved via the
    configured :class:`~pywandahydra.wanda.model_access.WandaModelAccess`, so it
    can be an exact name **or** a keyword that matches multiple items.

    The returned DataFrame has:

    * **index** – simulation time steps (``time [s]``).
    * **columns** – a :class:`~pandas.MultiIndex` of
      ``(component, property, s_location)``. For non-pipe components
      ``s_location`` is ``NaN``; for pipes it holds the distance from
      the pipe start in metres.

    Parameters
    ----------
    model : pywanda.WandaModel
        An open WANDA model that has been simulated.
    specs : Sequence[MinMaxTableSpecification]
        One or more export-table specifications.
    adapter : WandaModelAccess
        Adapter used for item resolution and unit-converted outputs.

    Returns
    -------
    pd.DataFrame
        Combined multi-header DataFrame.  Empty when *specs* is empty.
    """
    if not specs:
        return pd.DataFrame()

    time_steps = adapter.get_time_steps(model)
    n_times = len(time_steps)
    time_index = pd.Index(time_steps, name="time [s]")
    column_names = ["component", "property", "s_location"]

    frames: list[pd.DataFrame] = []
    seen: set[tuple[str, str]] = set()
    for spec in specs:
        item_names = adapter.resolve_output_items(model, spec.component)
        if not item_names:
            logger.warning(
                "Component '%s' not found in model – skipping.",
                spec.component,
            )
            continue
        for item_name in item_names:
            key = (item_name, spec.property)
            if key in seen:
                continue
            seen.add(key)

            try:
                is_pipe = adapter.is_pipe_item(model, item_name)
            except Exception:
                logger.debug(
                    "Component '%s' has no property '%s' - skipping.",
                    item_name,
                    spec.property,
                )
                continue

            if is_pipe:
                arr = _normalise_pipe_series(
                    np.asarray(
                        adapter.get_pipe_series(model, item_name, spec.property),
                        dtype=float,
                    ),
                    n_times,
                    item_name,
                    spec.property,
                )

                n_s = arr.shape[1]
                length = adapter.get_pipe_length(model, item_name)
                s_distance = np.linspace(0.0, length, n_s)
                tuples = [(item_name, spec.property, float(s)) for s in s_distance]
                data = arr
            else:
                arr = np.asarray(
                    adapter.get_series(model, item_name, spec.property),
                    dtype=float,
                )
                tuples = [(item_name, spec.property, np.nan)]
                data = arr.reshape(-1, 1)

            col = pd.MultiIndex.from_tuples(tuples, names=column_names)
            n_rows = min(len(data), n_times) if n_times else len(data)
            df = pd.DataFrame(
                data[:n_rows],
                index=time_index[:n_rows] if n_times else None,
                columns=col,
            )
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    # All frames share the same 3-level column schema, so concat + sort is unambiguous.
    frames_combined = pd.concat(frames, axis=1)
    frames_combined = frames_combined.sort_index(axis=1, level=[0, 1, 2])
    frames_combined = frames_combined.loc[:, ~frames_combined.columns.duplicated()]
    return frames_combined


# ---------------------------------------------------------------------------
# Route extraction  (RPlots sheet specifications)
# ---------------------------------------------------------------------------


def extract_route_outputs(
    model: pywanda.WandaModel,
    specs: Sequence[RoutePlotSpecification],
    adapter: WandaModelAccess,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Extract route-based property data for every *RPlots* specification.

    Each specification describes a route plot with axis metadata.  The
    ``title`` field from the specification is used as the dictionary key
    so that downstream code can correlate results with the plot they
    belong to.

    Each inner result dict contains DataFrames for route rendering:

    * ``"timeseries"`` – index ``time [s]``, columns a three-level
      :class:`~pandas.MultiIndex` ``(component, property, s_location)``.
      ``s_location`` is the *cumulative* distance along the full route in
      metres; pipes traversed in the reverse direction have their s-axis
      and data columns flipped accordingly.
    * ``"envelope"`` – index ``s_location [m]`` (cumulative along the
      route), columns ``["min", "max"]`` derived from
            :meth:`get_extr_min_pipe` / :meth:`get_extr_max_pipe`.
        * ``"profile"`` – index ``s_location [m]`` (cumulative along the
            route), column ``"elevation"`` from pipe profile tables.

    Parameters
    ----------
    model : pywanda.WandaModel
        An open WANDA model that has been simulated.
    specs : Sequence[RoutePlotSpecification]
        One or more route-plot specifications.
    adapter : WandaModelAccess
        Adapter used to resolve route topology and model outputs.

    Returns
    -------
    Dict[str, Dict[str, pd.DataFrame]]
        Mapping of specification *title* →
        ``{"timeseries": DataFrame, "envelope": DataFrame,
        "profile": DataFrame}``.
        Empty dict when *specs* is empty.
    """
    if not specs:
        return {}

    time_steps = adapter.get_time_steps(model)
    n_times = len(time_steps)
    time_index = pd.Index(time_steps, name="time [s]")
    ts_col_names = ["component", "property", "s_location"]

    results: dict[str, dict[str, pd.DataFrame]] = {}
    seen_keys: set[str] = set()

    for spec in specs:
        route_id = spec.route_id.strip()
        if not route_id:
            logger.warning(
                "Route spec with title '%s' has an empty route_id – skipping.",
                spec.title,
            )
            continue
        prop_name = spec.property.strip()

        pipes_with_dir = adapter.resolve_route_pipes(model, route_id)
        if not pipes_with_dir:
            logger.warning("Route identifier '%s' has no pipe components – skipping.", route_id)
            continue

        ts_frames: list[pd.DataFrame] = []
        env_rows: list[dict] = []
        profile_rows: list[dict[str, float]] = []
        s_offset = 0.0

        for pipe_name, direction in pipes_with_dir:
            try:
                length = adapter.get_pipe_length(model, pipe_name)
            except Exception:
                logger.debug("Pipe '%s' could not get Length – skipping.", pipe_name)
                continue

            # --- Timeseries (time × s_location) ---
            try:
                ts_arr = _normalise_pipe_series(
                    np.asarray(
                        adapter.get_pipe_series(model, pipe_name, prop_name),
                        dtype=float,
                    ),
                    n_times,
                    pipe_name,
                    prop_name,
                )
                n_s = ts_arr.shape[1] if ts_arr.ndim == 2 else 1
                s_local = np.linspace(0.0, length, n_s)
                s_cumul = s_offset + (s_local if direction > 0 else (length - s_local))
                if direction < 0:
                    ts_arr = ts_arr[:, ::-1]
                n_rows = min(len(ts_arr), n_times) if n_times else len(ts_arr)
                col = pd.MultiIndex.from_tuples(
                    [(pipe_name, prop_name, float(s)) for s in s_cumul],
                    names=ts_col_names,
                )
                df_ts = pd.DataFrame(
                    ts_arr[:n_rows],
                    index=time_index[:n_rows] if n_times else None,
                    columns=col,
                )
                ts_frames.append(df_ts)
            except Exception:
                logger.debug(
                    "Pipe '%s' property '%s' has no pipe series – skipping timeseries.",
                    pipe_name,
                    prop_name,
                )

            # --- Envelope (min / max along s_location) ---
            try:
                min_vals, max_vals = adapter.get_pipe_extrema(
                    model,
                    pipe_name,
                    prop_name,
                )
                min_vals = np.asarray(min_vals, dtype=float).ravel()
                max_vals = np.asarray(max_vals, dtype=float).ravel()
                n_s_env = min(len(min_vals), len(max_vals))
                s_local_env = np.linspace(0.0, length, n_s_env)
                s_env = s_offset + (s_local_env if direction > 0 else (length - s_local_env))
                if direction < 0:
                    min_vals = min_vals[:n_s_env][::-1]
                    max_vals = max_vals[:n_s_env][::-1]
                for s, mn, mx in zip(s_env, min_vals[:n_s_env], max_vals[:n_s_env], strict=False):
                    env_rows.append({"s_location [m]": float(s), "min": mn, "max": mx})
            except Exception:
                logger.debug(
                    "Pipe '%s' property '%s' has no min/max series – skipping envelope.",
                    pipe_name,
                    prop_name,
                )

            # --- Elevation profile (s_location × elevation) ---
            try:
                profile_raw = np.asarray(
                    adapter.get_pipe_profile_table(model, pipe_name), dtype=float
                )
                if profile_raw.ndim == 2 and profile_raw.shape[0] >= 3:
                    profile_sh = profile_raw[:3].transpose()[:, -1:0:-1]
                    s_local_prof = profile_sh[:, 0]
                    elev_prof = profile_sh[:, 1]
                    if direction < 0:
                        s_local_prof = length - s_local_prof
                        s_local_prof = s_local_prof[::-1]
                        elev_prof = elev_prof[::-1]

                    s_prof = s_offset + s_local_prof
                    for s, elev in zip(s_prof, elev_prof, strict=False):
                        profile_rows.append(
                            {
                                "s_location [m]": float(s),
                                "elevation": float(elev),
                            }
                        )
            except Exception:
                logger.debug(
                    "Pipe '%s' has no profile data – skipping elevation profile.",
                    pipe_name,
                )

            s_offset += length

        # --- Assemble per-route result ---
        key = spec.title or f"{spec.route_id}_{spec.property}"
        if key in seen_keys:
            suffix = 2
            while f"{key}_{suffix}" in seen_keys:
                suffix += 1
            logger.warning("Duplicate route result key '%s' – stored as '%s_%d'.", key, key, suffix)
            key = f"{key}_{suffix}"
        seen_keys.add(key)

        route_result: dict[str, pd.DataFrame] = {}
        if ts_frames:
            route_result["timeseries"] = pd.concat(ts_frames, axis=1)
        if env_rows:
            route_result["envelope"] = pd.DataFrame(env_rows).set_index("s_location [m]")
        if profile_rows:
            profile_df = pd.DataFrame(profile_rows).set_index("s_location [m]")
            profile_df = profile_df.sort_index().groupby(level=0).mean()
            route_result["profile"] = profile_df
        if route_result:
            results[key] = route_result

    return results


def _normalise_pipe_series(
    arr: np.ndarray,
    n_times: int,
    pipe_name: str,
    prop_name: str,
) -> np.ndarray:
    """Return a pipe series array normalised to shape ``(t, s)``.

    The WANDA API may return either ``(t, s)`` or ``(s, t)``.  When the
    array is square (``n_s == n_t``) the first axis is assumed to be time.
    """
    if arr.ndim != 2:
        return arr
    if arr.shape[0] != n_times and arr.shape[1] == n_times:
        return arr.T
    if arr.shape[0] == arr.shape[1] == n_times:
        logger.debug(
            "Pipe '%s' property '%s' series is square (%d x %d); assuming first axis is time.",
            pipe_name,
            prop_name,
            n_times,
            n_times,
        )
    return arr


# ---------------------------------------------------------------------------
# Convenience: extract everything from a ScenarioSpecification
# ---------------------------------------------------------------------------


def extract_all(
    model: pywanda.WandaModel,
    scenario: ScenarioSpecification,
    adapter: WandaModelAccess,
) -> dict[str, Any]:
    """Run all extractions defined on a scenario specification.

    Parameters
    ----------
    model : pywanda.WandaModel
        An open WANDA model that has been simulated.
    scenario : ScenarioSpecification
        The scenario whose ``tables``, ``time_plots`` and ``routes``
        post-processing lists drive the extraction.
    adapter : WandaModelAccess
        Adapter used for route-related model operations.

    Returns
    -------
    dict[str, Any]
        ``{"components": DataFrame,
        "routes": dict[str, dict[str, DataFrame]]}``.
        Inner ``"routes"`` values have keys ``"timeseries"``,
        ``"envelope"`` and optionally ``"profile"``.
    """
    # Time plots read from the same components cache, so their
    # (component, property) pairs are extracted alongside the Output sheet
    # specifications; duplicates are de-duplicated inside the extractor.
    component_specs: list[MinMaxTableSpecification | TimeSeriesPlotSpecification] = [
        *scenario.post_processing.tables.minmax,
        *scenario.post_processing.figures.time_series,
    ]
    return {
        "components": extract_component_outputs(
            model,
            component_specs,
            adapter,
        ),
        "routes": extract_route_outputs(
            model,
            scenario.post_processing.figures.routes,
            adapter,
        ),
    }
