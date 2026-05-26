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
            prop = item.get_property(spec.property)
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

        # Resolve the route identifier from the legend field
        item_refs = resolve_items(model, route_id)
        if not item_refs:
            logger.warning(
                "Route identifier '%s' not found in model – skipping.",
                route_id,
            )
            continue

        time_steps = model.get_time_steps()

        frames: list[pd.DataFrame] = []
        for ref in item_refs:
            item = get_item(model, ref)

            prop = item.get_property(prop_name)
            series: list[float] = prop.get_series()

            col = pd.MultiIndex.from_tuples(
                [(ref.name, prop_name)],
                names=["component", "property"],
            )
            df = pd.DataFrame(
                series,
                index=pd.Index(time_steps[: len(series)], name="time [s]"),
                columns=col,
            )
            frames.append(df)

        if frames:
            key = spec.title or f"{spec.route_id}_{spec.property}"
            results[key] = pd.concat(frames, axis=1)

    return results


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
