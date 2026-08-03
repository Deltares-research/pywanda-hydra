"""Excel post-processing sheet parsing."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

import pandas as pd
from pydantic import ValidationError

from ..models.document import ScenarioWarning
from ..models.plot_axis import AxisSpecification
from ..models.plot_route import RoutePlotSpecification
from ..models.table import MinMaxTableSpecification
from ..models.time_series_plot import TimeSeriesPlotSpecification
from .validation import ScenarioValidationError

if TYPE_CHECKING:
    from ..loader import ScenarioLoadOptions


_SpecT = TypeVar("_SpecT")
_RowGetter = Callable[[str], Any]


def _is_nan(x: Any) -> bool:
    """Return ``True`` when a value should be treated as NaN/empty."""

    try:
        return bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def _as_str_or_none(x: Any) -> str | None:
    """Convert a cell value to a stripped string or ``None``."""

    if _is_nan(x) or x is None:
        return None
    s = str(x).strip()
    return s or None


def _float_or_none(val: Any) -> float | None:
    """Convert a value to ``float``; return ``None`` for missing/unparsable."""

    if _is_nan(val) or val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _add_warning(
    warnings_list: list[ScenarioWarning],
    *,
    sheet: str,
    message: str,
    row: int | None = None,
    column: str | None = None,
    expected_shape: str | None = None,
) -> None:
    """Append one typed parse warning to a warning sink."""

    warnings_list.append(
        ScenarioWarning(
            sheet=sheet,
            message=message,
            row=row,
            column=column,
            expected_shape=expected_shape,
        )
    )


def _read_output_sheet(
    path: str | Path,
    opts: ScenarioLoadOptions,
    *,
    warnings_list: list[ScenarioWarning] | None = None,
) -> list[MinMaxTableSpecification]:
    """Parse the Output sheet into min/max table specifications.

    Missing or malformed rows are emitted as warnings and skipped in lenient
    mode. In strict mode (with no external warning sink), collected warnings are
    raised as one ``ScenarioValidationError``.
    """

    if opts.output_sheet is None:
        return []

    sink = warnings_list if warnings_list is not None else []

    try:
        df = cast(pd.DataFrame, pd.read_excel(path, opts.output_sheet, header=None))
    except ValueError as err:
        _add_warning(
            sink,
            sheet=opts.output_sheet,
            message=f"Sheet '{opts.output_sheet}' not found.",
            expected_shape="Output: [component, property, mode] columns",
        )
        if opts.strict_validation and warnings_list is None:
            raise ScenarioValidationError(
                sink,
                context=f"sheet '{opts.output_sheet}'",
            ) from err
        return []

    if df.shape[1] < 3:
        _add_warning(
            sink,
            sheet=opts.output_sheet,
            message=f"sheet must have at least 3 columns; found {df.shape[1]}.",
            expected_shape="Output: [component, property, mode] columns",
        )
        if opts.strict_validation and warnings_list is None:
            raise ScenarioValidationError(sink, context=f"sheet '{opts.output_sheet}'")
        return []

    specs: list[MinMaxTableSpecification] = []
    seen: set[tuple[str, str]] = set()
    for idx, row in df.iterrows():
        comp = _as_str_or_none(row.iloc[0])
        prop = _as_str_or_none(row.iloc[1])
        mode_str = _as_str_or_none(row.iloc[2])

        if comp is None and prop is None and mode_str is None:
            continue

        if comp is None or prop is None or mode_str is None:
            _add_warning(
                sink,
                sheet=opts.output_sheet,
                row=int(idx),
                message=(
                    "incomplete row for output spec: "
                    f"component={comp!r}, property={prop!r}, mode={mode_str!r}."
                ),
                expected_shape="Output row: component, property, mode",
            )
            continue

        key = (comp, prop)
        if key in seen:
            _add_warning(
                sink,
                sheet=opts.output_sheet,
                row=int(idx),
                message=f"duplicate (component, property)=({comp!r}, {prop!r}).",
                expected_shape="Output row: unique (component, property)",
            )
        seen.add(key)

        try:
            specs.append(
                MinMaxTableSpecification(component=comp, property=prop, mode=cast(Any, mode_str))
            )
        except ValidationError as exc:
            _add_warning(
                sink,
                sheet=opts.output_sheet,
                row=int(idx),
                message=f"Invalid output row: {exc}",
                expected_shape="Output row: component(str), property(str), mode(MIN|MAX)",
            )

    if opts.strict_validation and warnings_list is None and sink:
        raise ScenarioValidationError(sink, context=f"sheet '{opts.output_sheet}'")

    return specs


def _parse_plot_sheet(
    path: str | Path,
    sheet: str,
    *,
    strict: bool,
    kind: str,
    build_spec: Callable[
        [_RowGetter, str, str, str | None, AxisSpecification, AxisSpecification],
        _SpecT,
    ],
    warnings_list: list[ScenarioWarning] | None = None,
) -> list[_SpecT]:
    """Shared parser for Rplots/Tplots sheet layouts.

    Required keys are resolved case-insensitively. Invalid rows become warnings
    and are skipped. In strict mode (without an external warning sink), warnings
    are promoted to one collected error.
    """

    sink = warnings_list if warnings_list is not None else []

    try:
        df = cast(pd.DataFrame, pd.read_excel(path, sheet))
    except ValueError as err:
        _add_warning(
            sink,
            sheet=sheet,
            message=f"Sheet '{sheet}' not found.",
            expected_shape=f"{sheet}: columns title,name,property (case-insensitive)",
        )
        if strict and warnings_list is None:
            raise ScenarioValidationError(sink, context=f"sheet '{sheet}'") from err
        return []

    columns_ci = {str(c).strip().lower(): c for c in df.columns}
    required_cols = {"title", "name", "property"}
    missing = required_cols - set(columns_ci)
    if missing:
        _add_warning(
            sink,
            sheet=sheet,
            message=f"missing required column(s): {sorted(missing)}",
            expected_shape=f"{sheet}: columns title,name,property (case-insensitive)",
        )
        if strict and warnings_list is None:
            raise ScenarioValidationError(sink, context=f"sheet '{sheet}'")
        return []

    specs: list[_SpecT] = []
    seen_titles: set[str] = set()

    for idx, row in df.iterrows():

        def get(key: str, row: pd.Series = row) -> Any:
            actual = columns_ci.get(key.lower())
            return row.get(actual) if actual is not None else None

        comp = _as_str_or_none(get("name"))
        prop = _as_str_or_none(get("property"))

        if comp is None and prop is None:
            continue

        if comp is None or prop is None:
            _add_warning(
                sink,
                sheet=sheet,
                row=int(idx),
                message=f"incomplete row: name={comp!r}, property={prop!r}.",
                expected_shape=f"{kind} row: name, property, title",
            )
            continue

        title = _as_str_or_none(get("title"))
        if title is not None:
            if title in seen_titles:
                _add_warning(
                    sink,
                    sheet=sheet,
                    row=int(idx),
                    column="title",
                    message=f"duplicate {kind} title {title!r}.",
                    expected_shape="Titles should be unique per sheet",
                )
            seen_titles.add(title)

        x_axis = AxisSpecification(
            label=_as_str_or_none(get("xlabel")) or "",
            min=_float_or_none(get("xmin")),
            max=_float_or_none(get("xmax")),
            tick_interval=_float_or_none(get("xtick")),
            factor=_float_or_none(get("xscale")) or 1.0,
        )
        y_axis = AxisSpecification(
            label=_as_str_or_none(get("ylabel")) or "",
            min=_float_or_none(get("ymin")),
            max=_float_or_none(get("ymax")),
            tick_interval=_float_or_none(get("ytick")),
            factor=_float_or_none(get("yscale")) or 1.0,
        )

        try:
            specs.append(build_spec(get, comp, prop, title, x_axis, y_axis))
        except ValidationError as exc:
            _add_warning(
                sink,
                sheet=sheet,
                row=int(idx),
                message=f"Invalid {kind} row: {exc}",
                expected_shape=f"{kind} row fields must match schema",
            )

    if strict and warnings_list is None and sink:
        raise ScenarioValidationError(sink, context=f"sheet '{sheet}'")

    return specs


def _read_rplots_sheet(
    path: str | Path,
    opts: ScenarioLoadOptions,
    *,
    warnings_list: list[ScenarioWarning] | None = None,
) -> list[RoutePlotSpecification]:
    """Parse the Rplots sheet into route-plot specifications."""

    if opts.rplots_sheet is None:
        return []

    def build_spec(
        get: _RowGetter,
        comp: str,
        prop: str,
        title: str | None,
        x_axis: AxisSpecification,
        y_axis: AxisSpecification,
    ) -> RoutePlotSpecification:
        """Build one route spec from a normalized row getter."""

        return RoutePlotSpecification(
            route_id=comp,
            property=prop,
            title=title,
            legend=_as_str_or_none(get("legend")),
            fig=_as_str_or_none(get("fig")),
            plot=get("plot"),
            x_axis=x_axis,
            y_axis=y_axis,
        )

    return _parse_plot_sheet(
        path,
        opts.rplots_sheet,
        strict=opts.strict_validation,
        kind="route",
        build_spec=build_spec,
        warnings_list=warnings_list,
    )


def _read_tplots_sheet(
    path: str | Path,
    opts: ScenarioLoadOptions,
    *,
    warnings_list: list[ScenarioWarning] | None = None,
) -> list[TimeSeriesPlotSpecification]:
    """Parse the Tplots sheet into time-series plot specifications."""

    if opts.tplots_sheet is None:
        return []

    def build_spec(
        get: _RowGetter,
        comp: str,
        prop: str,
        title: str | None,
        x_axis: AxisSpecification,
        y_axis: AxisSpecification,
    ) -> TimeSeriesPlotSpecification:
        """Build one time-series spec from a normalized row getter."""

        return TimeSeriesPlotSpecification(
            component=comp,
            property=prop,
            title=title,
            legend=_as_str_or_none(get("legend")),
            fig=_as_str_or_none(get("fig")),
            plot=get("plot"),
            location=_float_or_none(get("location")),
            color=_as_str_or_none(get("color")),
            style=_as_str_or_none(get("style")),
            marker=_as_str_or_none(get("marker")),
            x_axis=x_axis,
            y_axis=y_axis,
        )

    return _parse_plot_sheet(
        path,
        opts.tplots_sheet,
        strict=opts.strict_validation,
        kind="time-plot",
        build_spec=build_spec,
        warnings_list=warnings_list,
    )
