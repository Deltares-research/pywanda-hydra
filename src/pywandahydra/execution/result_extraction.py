"""Extract WANDA simulation outputs into WANDA-free result contracts."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Literal

import numpy as np
import pandas as pd

from ..results import (
    ComponentIdentity,
    ComponentTimeSeries,
    DataRequirements,
    ExtractedSimulationData,
    RouteData,
    RouteIdentity,
    RouteProductIdentity,
)
from ..scenarios import (
    ScenarioSpecification,
)
from ..wanda.model_access import ModelHandle, WandaModelAccess

logger = logging.getLogger(__name__)


def requirements_from_scenario(scenario: ScenarioSpecification) -> DataRequirements:
    """Derive the raw data required for a scenario's configured outputs."""
    product_names: tuple[Literal["timeseries", "envelope", "profile"], ...] = (
        "timeseries",
        "envelope",
        "profile",
    )
    components = frozenset(
        ComponentIdentity(spec.component, spec.property)
        for spec in scenario.post_processing.tables.minmax
    ) | frozenset(
        ComponentIdentity(spec.component, spec.property, spec.location)
        for spec in scenario.post_processing.figures.time_series
    )
    route_product_requirements = frozenset(
        RouteProductIdentity(RouteIdentity(spec.route_id, spec.property), product)
        for spec in scenario.post_processing.figures.routes
        for product in product_names
    )
    return DataRequirements(components=components, route_products=route_product_requirements)


def extract_simulation_data(
    model: ModelHandle,
    access: WandaModelAccess,
    requirements: DataRequirements,
) -> ExtractedSimulationData:
    """Extract requested simulation data using only the WANDA access protocol."""
    return ExtractedSimulationData(
        components=ComponentTimeSeries(_extract_components(model, access, requirements.components)),
        routes=_extract_routes(model, access, requirements.route_products),
    )


def _extract_components(
    model: ModelHandle,
    access: WandaModelAccess,
    requirements: Iterable[ComponentIdentity],
) -> pd.DataFrame:
    time_steps = access.get_time_steps(model)
    time_index = pd.Index(time_steps, name="time [s]")
    frames: list[pd.DataFrame] = []
    seen: set[tuple[str, str]] = set()

    for requirement in sorted(requirements):
        for item_name in access.resolve_output_items(model, requirement.component):
            key = (item_name, requirement.property)
            if key in seen:
                continue
            seen.add(key)
            try:
                frame = _extract_component_frame(
                    model, access, item_name, requirement.property, time_index
                )
            except Exception:
                logger.debug(
                    "Component '%s' property '%s' could not be extracted.",
                    item_name,
                    requirement.property,
                    exc_info=True,
                )
                continue
            frames.append(frame)

    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, axis=1).sort_index(axis=1, level=[0, 1, 2])
    return data.loc[:, ~data.columns.duplicated()]


def _extract_component_frame(
    model: ModelHandle,
    access: WandaModelAccess,
    item_name: str,
    property_name: str,
    time_index: pd.Index[float],
) -> pd.DataFrame:
    if access.is_pipe_item(model, item_name):
        values = _normalise_pipe_series(
            np.asarray(access.get_pipe_series(model, item_name, property_name), dtype=float),
            len(time_index),
        )
        locations = np.linspace(0.0, access.get_pipe_length(model, item_name), values.shape[1])
        columns = [(item_name, property_name, float(location)) for location in locations]
    else:
        values = np.asarray(
            access.get_series(model, item_name, property_name), dtype=float
        ).reshape(-1, 1)
        columns = [(item_name, property_name, np.nan)]

    row_count = min(len(values), len(time_index))
    return pd.DataFrame(
        values[:row_count],
        index=time_index[:row_count],
        columns=pd.MultiIndex.from_tuples(
            columns, names=["component", "property", "s_location"]
        ),
    )


def _extract_routes(
    model: ModelHandle,
    access: WandaModelAccess,
    requirements: Iterable[RouteProductIdentity],
) -> dict[RouteIdentity, RouteData]:
    products_by_route: dict[RouteIdentity, set[str]] = {}
    for requirement in requirements:
        products_by_route.setdefault(requirement.route, set()).add(requirement.product)

    time_steps = access.get_time_steps(model)
    time_index = pd.Index(time_steps, name="time [s]")
    extracted: dict[RouteIdentity, RouteData] = {}
    for identity, products in sorted(products_by_route.items()):
        pipes = access.resolve_route_pipes(model, identity.route_id)
        if not pipes:
            logger.warning("Route identifier '%s' has no pipe components.", identity.route_id)
            continue
        extracted[identity] = _extract_route(model, access, identity, products, pipes, time_index)
    return extracted


def _extract_route(
    model: ModelHandle,
    access: WandaModelAccess,
    identity: RouteIdentity,
    products: set[str],
    pipes: list[tuple[str, int]],
    time_index: pd.Index[float],
) -> RouteData:
    timeseries: list[pd.DataFrame] = []
    envelope_rows: list[dict[str, float]] = []
    profile_rows: list[dict[str, float]] = []
    offset = 0.0
    for pipe_name, direction in pipes:
        try:
            length = access.get_pipe_length(model, pipe_name)
        except Exception:
            logger.debug("Route pipe '%s' has no length.", pipe_name, exc_info=True)
            continue
        if "timeseries" in products:
            try:
                values = _normalise_pipe_series(
                    np.asarray(
                        access.get_pipe_series(model, pipe_name, identity.property), dtype=float
                    ),
                    len(time_index),
                )
                locations = np.linspace(0.0, length, values.shape[1])
                if direction < 0:
                    values = values[:, ::-1]
                    locations = length - locations[::-1]
                row_count = min(len(values), len(time_index))
                timeseries.append(
                    pd.DataFrame(
                        values[:row_count],
                        index=time_index[:row_count],
                        columns=pd.Index(offset + locations, name="s_location [m]"),
                    )
                )
            except Exception:
                logger.debug("Route pipe '%s' has no time series.", pipe_name, exc_info=True)
        if "envelope" in products:
            try:
                minimum, maximum = access.get_pipe_extrema(model, pipe_name, identity.property)
                minimum = np.asarray(minimum, dtype=float).ravel()
                maximum = np.asarray(maximum, dtype=float).ravel()
                count = min(len(minimum), len(maximum))
                locations = np.linspace(0.0, length, count)
                if direction < 0:
                    locations = length - locations[::-1]
                    minimum = minimum[:count][::-1]
                    maximum = maximum[:count][::-1]
                envelope_rows.extend(
                    {"s_location [m]": float(location + offset), "min": low, "max": high}
                    for location, low, high in zip(
                        locations, minimum[:count], maximum[:count], strict=False
                    )
                )
            except Exception:
                logger.debug("Route pipe '%s' has no envelope.", pipe_name, exc_info=True)
        if "profile" in products:
            try:
                profile = np.asarray(access.get_pipe_profile_table(model, pipe_name), dtype=float)
                if profile.ndim == 2 and profile.shape[0] >= 3:
                    locations, elevations = profile[:3].transpose()[:, -1:0:-1].T
                    if direction < 0:
                        locations = (length - locations)[::-1]
                        elevations = elevations[::-1]
                    profile_rows.extend(
                        {"s_location [m]": float(location + offset), "elevation": float(elevation)}
                        for location, elevation in zip(locations, elevations, strict=False)
                    )
            except Exception:
                logger.debug("Route pipe '%s' has no profile.", pipe_name, exc_info=True)
        offset += length

    envelope = pd.DataFrame(envelope_rows).set_index("s_location [m]") if envelope_rows else None
    profile_data = (
        pd.DataFrame(profile_rows).set_index("s_location [m]").groupby(level=0).mean()
        if profile_rows
        else None
    )
    return RouteData(
        timeseries=pd.concat(timeseries, axis=1) if timeseries else None,
        envelope=envelope,
        profile=profile_data,
    )


def _normalise_pipe_series(values: np.ndarray, time_count: int) -> np.ndarray:
    if values.ndim == 2 and values.shape[0] != time_count and values.shape[1] == time_count:
        return values.T
    return values
