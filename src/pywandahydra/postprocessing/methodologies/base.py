"""Methodology and post-processing step registries."""

from __future__ import annotations

import logging
from typing import Any, cast

from pydantic import BaseModel, Field

from ..protocols import CaseStep, Methodology, RunStep

logger = logging.getLogger(__name__)

_METHODOLOGY_CLASSES: dict[str, type[Any]] = {}
_CASE_STEP_CLASSES: dict[str, type[Any]] = {}
_RUN_STEP_CLASSES: dict[str, type[Any]] = {}


class StepSpec(BaseModel):
    """Declarative case/run step specification."""

    name: str
    params: dict[str, Any] = Field(default_factory=dict)


def register_methodology(methodology_class: type[Any]) -> type[Any]:
    """Register a methodology class by its declared name."""
    existing = _METHODOLOGY_CLASSES.get(methodology_class.name)
    if existing is not None:
        return existing
    _METHODOLOGY_CLASSES[methodology_class.name] = methodology_class
    logger.debug("Registered methodology: %s", methodology_class.name)
    return methodology_class


def get_methodology_class(name: str) -> type[Any]:
    """Look up a registered methodology class by name."""
    if name not in _METHODOLOGY_CLASSES:
        available = sorted(_METHODOLOGY_CLASSES.keys())
        raise KeyError(f"Unknown methodology: '{name}'. Available: {available}")
    return _METHODOLOGY_CLASSES[name]


def list_methodologies() -> list[str]:
    """Return names of all registered methodologies."""
    return sorted(_METHODOLOGY_CLASSES.keys())


def resolve_methodology(name: str, params: dict[str, Any] | None = None) -> Methodology:
    """Instantiate a registered methodology with validated params."""
    cls = get_methodology_class(name)
    validated = cls.Params.model_validate(params or {})
    return cast(Methodology, cls(validated))


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
