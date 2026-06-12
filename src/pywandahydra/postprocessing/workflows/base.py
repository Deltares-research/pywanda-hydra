"""Workflow and post-processing step registries."""

from __future__ import annotations

import logging
from typing import Any, cast

from pydantic import BaseModel, Field

from ..core.protocols import CaseStep, PostProcessingWorkflow, RunStep

logger = logging.getLogger(__name__)

_WORKFLOW_CLASSES: dict[str, type[Any]] = {}
_CASE_STEP_CLASSES: dict[str, type[Any]] = {}
_RUN_STEP_CLASSES: dict[str, type[Any]] = {}


class StepSpec(BaseModel):
    """Declarative case/run step specification."""

    name: str
    params: dict[str, Any] = Field(default_factory=dict)


def register_workflow(workflow_class: type[Any]) -> type[Any]:
    """Register a workflow class by its declared name."""
    existing = _WORKFLOW_CLASSES.get(workflow_class.name)
    if existing is not None:
        return existing
    _WORKFLOW_CLASSES[workflow_class.name] = workflow_class
    logger.debug("Registered workflow: %s", workflow_class.name)
    return workflow_class


def get_workflow_class(name: str) -> type[Any]:
    """Look up a registered workflow class by name."""
    if name not in _WORKFLOW_CLASSES:
        available = sorted(_WORKFLOW_CLASSES.keys())
        raise KeyError(f"Unknown workflow: '{name}'. Available: {available}")
    return _WORKFLOW_CLASSES[name]


def list_workflows() -> list[str]:
    """Return names of all registered workflows."""
    return sorted(_WORKFLOW_CLASSES.keys())


def resolve_workflow(
    name: str,
    params: dict[str, Any] | None = None,
) -> PostProcessingWorkflow:
    """Instantiate a registered workflow with validated params."""
    cls = get_workflow_class(name)
    validated = cls.Params.model_validate(params or {})
    return cast(PostProcessingWorkflow, cls(validated))


def register_case_step(step_class: type[Any]) -> type[Any]:
    """Register a case-level step class."""
    existing = _CASE_STEP_CLASSES.get(step_class.name)
    if existing is not None:
        return existing
    _CASE_STEP_CLASSES[step_class.name] = step_class
    logger.debug("Registered case step: %s", step_class.name)
    return step_class


def register_run_step(step_class: type[Any]) -> type[Any]:
    """Register a run-level step class."""
    existing = _RUN_STEP_CLASSES.get(step_class.name)
    if existing is not None:
        return existing
    _RUN_STEP_CLASSES[step_class.name] = step_class
    logger.debug("Registered run step: %s", step_class.name)
    return step_class


def list_case_steps() -> list[str]:
    return sorted(_CASE_STEP_CLASSES.keys())


def list_run_steps() -> list[str]:
    return sorted(_RUN_STEP_CLASSES.keys())


def get_case_step_class(name: str) -> type[Any]:
    """Look up a registered case step class by name."""
    if name not in _CASE_STEP_CLASSES:
        available = sorted(_CASE_STEP_CLASSES.keys())
        raise KeyError(f"Unknown case step: '{name}'. Available: {available}")
    return _CASE_STEP_CLASSES[name]


def get_run_step_class(name: str) -> type[Any]:
    """Look up a registered run step class by name."""
    if name not in _RUN_STEP_CLASSES:
        available = sorted(_RUN_STEP_CLASSES.keys())
        raise KeyError(f"Unknown run step: '{name}'. Available: {available}")
    return _RUN_STEP_CLASSES[name]


def build_case_step(spec: StepSpec) -> CaseStep:
    """Instantiate a registered case step from declarative StepSpec."""
    if spec.name not in _CASE_STEP_CLASSES:
        raise KeyError(
            f"Unknown case step '{spec.name}'. Available: {list_case_steps()}"
        )
    cls = _CASE_STEP_CLASSES[spec.name]
    params_model = cls.Params.model_validate(spec.params)
    return cast(CaseStep, cls(params_model))


def build_run_step(spec: StepSpec) -> RunStep:
    """Instantiate a registered run step from declarative StepSpec."""
    if spec.name not in _RUN_STEP_CLASSES:
        raise KeyError(f"Unknown run step '{spec.name}'. Available: {list_run_steps()}")
    cls = _RUN_STEP_CLASSES[spec.name]
    params_model = cls.Params.model_validate(spec.params)
    return cast(RunStep, cls(params_model))
