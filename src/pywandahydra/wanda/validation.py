"""Pre-run validation against an open WANDA model."""

from __future__ import annotations

import gc
import logging
from dataclasses import dataclass
from multiprocessing import get_context
from multiprocessing.connection import Connection
from typing import Any, cast

from ..config.models import ModelSpecification
from ..disuse import parse_disuse_value
from ..scenarios import ScenarioSpecification
from .item_lookup import get_item, resolve_items
from .session import wanda_session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationIssue:
    """Validation issue found during preflight checks."""

    scenario: str
    source: str
    component: str
    property_name: str
    message: str


class PreflightValidationError(ValueError):
    """Raised when preflight validation finds one or more issues."""


def _validate_component_property(
    model: Any,
    *,
    scenario: str,
    source: str,
    component: str,
    property_name: str,
    value: Any | None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if component.strip().lower() == "general":
        try:
            model.get_property(property_name)
        except Exception as exc:
            issues.append(
                ValidationIssue(
                    scenario=scenario,
                    source=source,
                    component=component,
                    property_name=property_name,
                    message=f"General property not found: {exc}",
                )
            )
        return issues

    try:
        item_refs = resolve_items(model, component)
    except Exception as exc:
        issues.append(
            ValidationIssue(
                scenario=scenario,
                source=source,
                component=component,
                property_name=property_name,
                message=f"Component resolution failed: {exc}",
            )
        )
        return issues

    if not item_refs:
        issues.append(
            ValidationIssue(
                scenario=scenario,
                source=source,
                component=component,
                property_name=property_name,
                message="Component not found in model (exact name or keyword match failed)",
            )
        )
        return issues

    if property_name.strip().lower() == "disuse":
        try:
            parse_disuse_value(value)
        except Exception as exc:
            issues.append(
                ValidationIssue(
                    scenario=scenario,
                    source=source,
                    component=component,
                    property_name=property_name,
                    message=str(exc),
                )
            )
        return issues

    has_property = False
    for ref in item_refs:
        try:
            item = get_item(model, ref)
            item.get_property(property_name)
            has_property = True
            break
        except Exception:
            continue

    if not has_property:
        issues.append(
            ValidationIssue(
                scenario=scenario,
                source=source,
                component=component,
                property_name=property_name,
                message="Property not found on any resolved items",
            )
        )

    return issues


def validate_scenarios_against_model(
    *,
    model_spec: ModelSpecification,
    scenarios: list[ScenarioSpecification],
) -> list[ValidationIssue]:
    """Validate scenario definitions against the base model before execution."""
    issues: list[ValidationIssue] = []

    with wanda_session(model_spec) as model:
        # Validate scenario parameters and post-processing specs
        for scenario in scenarios:
            scenario_name = scenario.name

            for change in scenario.parameter_changes:
                issues.extend(
                    _validate_component_property(
                        model,
                        scenario=scenario_name,
                        source="parameters",
                        component=change.component,
                        property_name=change.property,
                        value=change.value,
                    )
                )

            for table_spec in scenario.post_processing.tables.minmax:
                issues.extend(
                    _validate_component_property(
                        model,
                        scenario=scenario_name,
                        source="post_processing.tables",
                        component=table_spec.component,
                        property_name=table_spec.property,
                        value=None,
                    )
                )

            for route_spec in scenario.post_processing.figures.routes:
                issues.extend(
                    _validate_component_property(
                        model,
                        scenario=scenario_name,
                        source="post_processing.routes",
                        component=route_spec.route_id,
                        property_name=route_spec.property,
                        value=None,
                    )
                )

            for time_spec in scenario.post_processing.figures.time_series:
                issues.extend(
                    _validate_component_property(
                        model,
                        scenario=scenario_name,
                        source="post_processing.time_plots",
                        component=time_spec.component,
                        property_name=time_spec.property,
                        value=None,
                    )
                )

        # Release any lingering pywanda wrapper objects (items/properties
        # point into native model memory) before the model is closed.
        gc.collect()

    return issues


def _preflight_worker(
    conn: Connection,
    model_spec: ModelSpecification,
    scenarios: list[ScenarioSpecification],
) -> None:
    """Spawn entry point: run validation and report back over a pipe."""
    try:
        issues = validate_scenarios_against_model(
            model_spec=model_spec,
            scenarios=scenarios,
        )
        conn.send(("ok", issues))
    except Exception as exc:
        conn.send(("error", exc))
    finally:
        conn.close()


def _validate_in_subprocess(
    *,
    model_spec: ModelSpecification,
    scenarios: list[ScenarioSpecification],
) -> list[ValidationIssue]:
    """Run preflight validation in a spawned child process.

    pywanda/WANDA tolerates only one model open per process lifetime
    reliably; isolating the preflight open keeps the main (sequential)
    process free of any prior native model state before cases run.
    """
    ctx = get_context("spawn")
    recv_conn, send_conn = ctx.Pipe(duplex=False)
    process = ctx.Process(
        target=_preflight_worker,
        args=(send_conn, model_spec, scenarios),
    )
    logger.debug("Starting preflight validation subprocess...")
    process.start()
    # Close the parent's copy of the send end so a child crash surfaces as
    # EOFError on recv() instead of blocking forever.
    send_conn.close()
    try:
        status, payload = recv_conn.recv()
    except EOFError:
        process.join()
        raise RuntimeError(
            "Preflight validation subprocess terminated unexpectedly "
            f"(exit code {process.exitcode}). This usually indicates a "
            "native crash inside pywanda while opening the base model."
        ) from None
    finally:
        recv_conn.close()
    process.join()
    logger.debug("Preflight validation subprocess finished.")

    if status == "error":
        raise payload
    return cast(list[ValidationIssue], payload)


def assert_preflight_valid(
    *,
    model_spec: ModelSpecification,
    scenarios: list[ScenarioSpecification],
    isolated: bool = True,
) -> None:
    """Raise a single error with all validation findings, if any.

    Args:
        model_spec: Base model specification to validate against.
        scenarios: Scenario specifications to validate.
        isolated: Open the base model in a spawned subprocess (default) so
            the calling process never holds native WANDA state before case
            execution. Set False to validate in-process (e.g., in tests).
    """
    if isolated:
        issues = _validate_in_subprocess(
            model_spec=model_spec,
            scenarios=scenarios,
        )
    else:
        issues = validate_scenarios_against_model(
            model_spec=model_spec,
            scenarios=scenarios,
        )
    if not issues:
        return

    lines = [
        "Preflight validation failed. Please fix scenario definitions before running:",
    ]
    for issue in issues:
        lines.append(
            f"- [{issue.scenario}] {issue.source}: "
            f"{issue.component}.{issue.property_name} -> {issue.message}"
        )
    raise PreflightValidationError("\n".join(lines))

