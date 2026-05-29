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
    # results["routes"]      -> dict[str, DataFrame] keyed by route title
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Sequence

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
      ``(component, property)``.

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

    frames: list[pd.DataFrame] = []
    for spec in specs:
        item_refs = resolve_items(model, spec.component)
        if not item_refs:
            logger.warning(
                "Component '%s' not found in model – skipping.",
                spec.component,
            )
            continue
        # TODO: If exists in frames, skip.
        for ref in item_refs:
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

            series: list[float] = prop.get_series()

            col = pd.MultiIndex.from_tuples(
                [(ref.name, spec.property)],
                names=["component", "property"],
            )
            df = pd.DataFrame(
                series,
                index=pd.Index(time_steps[: len(series)], name="time [s]"),
                columns=col,
            )
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    # Concat all frames horizontally, aligning on time index
    frames_combined = pd.concat(frames, axis=1)

    # Sort Columns by component name, then property name
    frames_combined.sort_index(axis=1, level=[0, 1], inplace=True)
    # Drop duplicate columns if any (e.g. from overlapping keywords)
    frames_combined = frames_combined.loc[:, ~frames_combined.columns.duplicated()]
    return frames_combined


# ---------------------------------------------------------------------------
# Route extraction  (RPlots sheet specifications)
# ---------------------------------------------------------------------------


def extract_route_outputs(
    model: pywanda.WandaModel,
    specs: Sequence[RoutePlotSpecification],
) -> Dict[str, pd.DataFrame]:
    """Extract route-based property data for every *RPlots* specification.

    Each specification describes a route plot with axis metadata.  The
    ``title`` field from the specification is used as the dictionary key
    so that downstream code can correlate results with the plot they
    belong to.

    Each returned DataFrame has:

    * **index** – ``s_location [m]`` (distance along the route).
    * **columns** – a :class:`~pandas.MultiIndex` of
      ``(component, property)`` for every pipe / element on the route.

    .. note::

       The current implementation extracts the *full time series* for
       every component along the route.  Min/max extraction or sampling
       at specific times can be performed as a downstream step.

    Parameters
    ----------
    model : pywanda.WandaModel
        An open WANDA model that has been simulated.
    specs : Sequence[RoutePlotSpecification]
        One or more route-plot specifications.

    Returns
    -------
    Dict[str, pd.DataFrame]
        Mapping of specification *title* → DataFrame.
        Empty dict when *specs* is empty.
    """
    if not specs:
        return {}

    results: Dict[str, pd.DataFrame] = {}

    for spec in specs:
        route_id = spec.route_id.strip()
        prop_name = spec.property.strip()

        pipes = _resolve_route_pipes(model, route_id)
        if not pipes:
            logger.warning(
                "Route identifier '%s' has no pipe components – skipping.",
                route_id,
            )
            continue

        time_steps = model.get_time_steps()

        frames: list[pd.DataFrame] = []
        for pipe in pipes:
            try:
                prop = pipe.get_property(prop_name)
            except Exception:
                logger.debug(
                    "Pipe '%s' has no property '%s' – skipping.",
                    pipe.get_complete_name_spec(),
                    prop_name,
                )
                continue

            # Read route output for this pipe/property when the API exposes it.
            try:
                model.read_prop_output(prop)
            except Exception:
                pass

            try:
                pipe_series = prop.get_series_pipe()
            except Exception:
                logger.debug(
                    "Pipe '%s' property '%s' has no pipe series – skipping.",
                    pipe.get_complete_name_spec(),
                    prop_name,
                )
                continue

            pipe_df = _pipe_series_to_time_frame(
                pipe_name=pipe.get_complete_name_spec(),
                prop_name=prop_name,
                pipe_series=pipe_series,
                time_steps=time_steps,
            )
            if not pipe_df.empty:
                frames.append(pipe_df)

        if frames:
            key = spec.title or f"{spec.route_id}_{spec.property}"
            combined = pd.concat(frames, axis=1)
            combined = combined.sort_index(axis=1)
            results[key] = combined

    return results


def _resolve_route_pipes(model: pywanda.WandaModel, route_id: str) -> list[Any]:
    """Resolve and return only pipe components for a route identifier."""
    route_id = route_id.strip()
    if not route_id:
        return []

    # Preferred path: use native route resolution from pywanda.
    try:
        components, directions = model.get_route(route_id)
        pipes: list[Any] = []
        for comp, direction in zip(components, directions, strict=False):
            if direction == 0:
                continue
            if hasattr(comp, "is_pipe") and comp.is_pipe():
                pipes.append(comp)
        if pipes:
            return pipes
    except Exception:
        pass

    # Fallback path: resolve by identifier and keep only pipe components.
    item_refs = resolve_items(model, route_id)
    pipes = []
    for ref in item_refs:
        try:
            item = get_item(model, ref)
        except Exception:
            continue
        if hasattr(item, "is_pipe") and item.is_pipe():
            pipes.append(item)
    return pipes


def _pipe_series_to_time_frame(
    *,
    pipe_name: str,
    prop_name: str,
    pipe_series: Any,
    time_steps: list[float],
) -> pd.DataFrame:
    """Convert a WANDA pipe-series array to a time-indexed DataFrame.

    The WANDA API may return shape [s, t] or [t, s]. This function
    normalizes to [t, s] and creates one column per s-location.
    """
    raw = pd.DataFrame(pipe_series)
    if raw.empty:
        return pd.DataFrame()

    n_times = len(time_steps)
    if n_times > 0:
        if raw.shape[1] == n_times:
            raw = raw.T
        elif raw.shape[0] != n_times:
            logger.debug(
                "Pipe '%s' property '%s' series shape %s does not match %d timesteps; "
                "truncating by first axis.",
                pipe_name,
                prop_name,
                tuple(raw.shape),
                n_times,
            )

    if n_times > 0:
        n_rows = min(len(raw), n_times)
        raw = raw.iloc[:n_rows, :]
        raw.index = pd.Index(time_steps[:n_rows], name="time [s]")

    raw.columns = pd.MultiIndex.from_tuples(
        [(pipe_name, f"{prop_name}[{i}]") for i in range(raw.shape[1])],
        names=["component", "property"],
    )
    return raw


# ---------------------------------------------------------------------------
# Convenience: extract everything from a ScenarioSpecification
# ---------------------------------------------------------------------------


def extract_all(
    model: pywanda.WandaModel,
    scenario: ScenarioSpecification,
) -> Dict[str, Any]:
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
        ``{"components": DataFrame, "routes": dict[str, DataFrame]}``.
    """
    return {
        "components": extract_component_outputs(model, scenario.outputs),
        "routes": extract_route_outputs(model, scenario.route_plots),
    }
