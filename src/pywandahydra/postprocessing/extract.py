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

    results = extract_all(model, scenario)
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

from ..scenarios.schema import (
    ExportTableSpecification,
    RoutePlotSpecification,
    ScenarioSpecification,
)
from ..wanda.api import get_item, resolve_items

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Component / keyword extraction  (Output sheet specifications)
# ---------------------------------------------------------------------------


def extract_component_outputs(
    model: pywanda.WandaModel,
    specs: Sequence[ExportTableSpecification],
) -> pd.DataFrame:
    """Extract time-series data for every *Output* specification.

    Each specification identifies a *component* (or keyword) and a
    *property*.  The component identifier is resolved via
    :func:`~pywandahydra.wanda.api.resolve_items`, so it can be an
    exact name **or** a keyword that matches multiple items.

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
    specs : Sequence[ExportTableSpecification]
        One or more export-table specifications.

    Returns
    -------
    pd.DataFrame
        Combined multi-header DataFrame.  Empty when *specs* is empty.
    """
    if not specs:
        return pd.DataFrame()

    time_steps = model.get_time_steps()
    n_times = len(time_steps)
    time_index = pd.Index(time_steps, name="time [s]")
    column_names = ["component", "property", "s_location"]

    frames: list[pd.DataFrame] = []
    seen: set[tuple[str, str]] = set()
    for spec in specs:
        item_refs = resolve_items(model, spec.component)
        if not item_refs:
            logger.warning(
                "Component '%s' not found in model – skipping.",
                spec.component,
            )
            continue
        for ref in item_refs:
            key = (ref.name, spec.property)
            if key in seen:
                continue
            seen.add(key)

            item = get_item(model, ref)
            try:
                prop = item.get_property(spec.property)
            except Exception:
                logger.debug(
                    "Component '%s' has no property '%s' - skipping.",
                    ref.name,
                    spec.property,
                )
                continue

            try:
                model.read_prop_output(prop)
            except Exception:
                # Some property types do not require explicit read calls.
                pass

            if item.is_pipe():
                arr = _normalise_pipe_series(
                    np.asarray(prop.get_series_pipe(), dtype=float),
                    n_times,
                    ref.name,
                    spec.property,
                )

                n_s = arr.shape[1]
                length = item.get_property("Length").get_scalar_float()
                s_distance = np.linspace(0.0, length, n_s)
                tuples = [(ref.name, spec.property, float(s)) for s in s_distance]
                data = arr
            else:
                arr = np.asarray(prop.get_series(), dtype=float)
                tuples = [(ref.name, spec.property, np.nan)]
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
) -> dict[str, dict[str, pd.DataFrame]]:
    """Extract route-based property data for every *RPlots* specification.

    Each specification describes a route plot with axis metadata.  The
    ``title`` field from the specification is used as the dictionary key
    so that downstream code can correlate results with the plot they
    belong to.

    Each inner result dict contains two DataFrames:

    * ``"timeseries"`` – index ``time [s]``, columns a three-level
      :class:`~pandas.MultiIndex` ``(component, property, s_location)``.
      ``s_location`` is the *cumulative* distance along the full route in
      metres; pipes traversed in the reverse direction have their s-axis
      and data columns flipped accordingly.
    * ``"envelope"`` – index ``s_location [m]`` (cumulative along the
      route), columns ``["min", "max"]`` derived from
      :meth:`get_series_pipe_min` / :meth:`get_series_pipe_max`.

    Parameters
    ----------
    model : pywanda.WandaModel
        An open WANDA model that has been simulated.
    specs : Sequence[RoutePlotSpecification]
        One or more route-plot specifications.

    Returns
    -------
    Dict[str, Dict[str, pd.DataFrame]]
        Mapping of specification *title* →
        ``{"timeseries": DataFrame, "envelope": DataFrame}``.
        Empty dict when *specs* is empty.
    """
    if not specs:
        return {}

    time_steps = model.get_time_steps()
    n_times = len(time_steps)
    time_index = pd.Index(time_steps, name="time [s]")
    ts_col_names = ["component", "property", "s_location"]

    results: dict[str, dict[str, pd.DataFrame]] = {}
    seen_keys: set[str] = set()

    for spec in specs:
        route_id = spec.route_id.strip()
        if not route_id:
            logger.warning(
                "Route spec with title '%s' has an empty route_id – skipping.", spec.title
            )
            continue
        prop_name = spec.property.strip()

        pipes_with_dir = _resolve_route_pipes(model, route_id)
        if not pipes_with_dir:
            logger.warning("Route identifier '%s' has no pipe components – skipping.", route_id)
            continue

        ts_frames: list[pd.DataFrame] = []
        env_rows: list[dict] = []
        s_offset = 0.0

        for pipe, direction in pipes_with_dir:
            pipe_name = pipe.get_complete_name_spec()

            try:
                length = pipe.get_property("Length").get_scalar_float()
            except Exception:
                logger.debug("Pipe '%s' could not get Length – skipping.", pipe_name)
                continue

            try:
                prop = pipe.get_property(prop_name)
            except Exception:
                logger.warning("Pipe '%s' has no property '%s' – skipping.", pipe_name, prop_name)
                s_offset += length
                continue

            try:
                model.read_prop_output(prop)
            except Exception:
                pass

            # --- Timeseries (time × s_location) ---
            try:
                ts_arr = _normalise_pipe_series(
                    np.asarray(prop.get_series_pipe(), dtype=float),
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
                min_vals = np.asarray(prop.get_series_pipe_min(), dtype=float).ravel()
                max_vals = np.asarray(prop.get_series_pipe_max(), dtype=float).ravel()
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
            "Pipe '%s' property '%s' series is square (%d x %d); " "assuming first axis is time.",
            pipe_name,
            prop_name,
            n_times,
            n_times,
        )
    return arr


def _resolve_route_pipes(model: pywanda.WandaModel, route_id: str) -> list[tuple[Any, int]]:
    """Resolve pipes for a route, returning ``(pipe, direction)`` pairs.

    *direction* is ``+1`` for forward traversal and ``-1`` for reverse.
    The fallback path (when the native route API is unavailable) assumes
    ``+1`` for every pipe.
    """
    route_id = route_id.strip()
    if not route_id:
        return []

    # Preferred path: use native route resolution from pywanda.
    try:
        components, directions = model.get_route(route_id)
        pipes: list[tuple[Any, int]] = []
        for comp, direction in zip(components, directions, strict=False):
            if direction == 0:
                continue
            if hasattr(comp, "is_pipe") and comp.is_pipe():
                pipes.append((comp, int(direction)))
        if pipes:
            return pipes
    except Exception:
        pass

    # Fallback path: resolve by identifier; assume forward direction.
    item_refs = resolve_items(model, route_id)
    pipes = []
    for ref in item_refs:
        try:
            item = get_item(model, ref)
        except Exception:
            continue
        if hasattr(item, "is_pipe") and item.is_pipe():
            pipes.append((item, 1))
    return pipes


# ---------------------------------------------------------------------------
# Convenience: extract everything from a ScenarioSpecification
# ---------------------------------------------------------------------------


def extract_all(
    model: pywanda.WandaModel,
    scenario: ScenarioSpecification,
) -> dict[str, Any]:
    """Run all extractions defined on a scenario specification.

    Parameters
    ----------
    model : pywanda.WandaModel
        An open WANDA model that has been simulated.
    scenario : ScenarioSpecification
        The scenario whose ``outputs`` and ``route_plots`` lists drive
        the extraction.

    Returns
    -------
    dict[str, Any]
        ``{"components": DataFrame,
        "routes": dict[str, dict[str, DataFrame]]}``.
        Inner ``"routes"`` values have keys ``"timeseries"`` and
        ``"envelope"``.
    """
    return {
        "components": extract_component_outputs(model, scenario.post_processing.tables),
        "routes": extract_route_outputs(model, scenario.post_processing.routes),
    }
