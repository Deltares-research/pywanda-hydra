"""Unit tests for postprocessing.core.pipeline.run_postprocessing."""

from __future__ import annotations

from typing import ClassVar
from unittest import mock

from pywandahydra.postprocessing.core.context import CaseContext
from pywandahydra.postprocessing.core.pipeline import run_postprocessing


class _FakeStep:
    """Fake CaseStep that always runs successfully."""

    name: ClassVar[str] = "fake_step"

    def __init__(self) -> None:
        self.run_called = False

    def applicable(self, ctx: CaseContext) -> bool:
        del ctx
        return True

    def run(self, ctx: CaseContext) -> None:
        del ctx
        self.run_called = True


class _SkippedStep(_FakeStep):
    name: ClassVar[str] = "skipped_step"

    def applicable(self, ctx: CaseContext) -> bool:
        del ctx
        return False


class _FailingStep(_FakeStep):
    name: ClassVar[str] = "failing_step"

    def run(self, ctx: CaseContext) -> None:
        del ctx
        self.run_called = True
        raise RuntimeError("boom")


class _FakeWorkflow:
    """Fake workflow returning a fixed list of case steps."""

    def __init__(self, steps: list[object]) -> None:
        self._steps = steps

    def case_steps(self, ctx: CaseContext) -> list[object]:
        del ctx
        return self._steps

    def run_steps(self, ctx: object) -> list[object]:
        del ctx
        return []


def test_step_runs_successfully(make_case_ctx) -> None:
    ctx = make_case_ctx()
    step = _FakeStep()
    workflow = _FakeWorkflow([step])

    with mock.patch(
        "pywandahydra.postprocessing.workflows.base.resolve_workflow",
        return_value=workflow,
    ):
        result = run_postprocessing(ctx, workflow_name="fake")

    assert result == {"fake_step": True}
    assert step.run_called


def test_step_skipped_when_not_applicable(make_case_ctx) -> None:
    ctx = make_case_ctx()
    step = _SkippedStep()
    workflow = _FakeWorkflow([step])

    with mock.patch(
        "pywandahydra.postprocessing.workflows.base.resolve_workflow",
        return_value=workflow,
    ):
        result = run_postprocessing(ctx, workflow_name="fake")

    assert result == {"skipped_step": True}
    assert not step.run_called


def test_step_exception_recorded_as_failure(make_case_ctx) -> None:
    ctx = make_case_ctx()
    step = _FailingStep()
    workflow = _FakeWorkflow([step])

    with mock.patch(
        "pywandahydra.postprocessing.workflows.base.resolve_workflow",
        return_value=workflow,
    ):
        result = run_postprocessing(ctx, workflow_name="fake")

    assert result == {"failing_step": False}
    assert step.run_called


def test_multiple_steps_result_dict_ordering(make_case_ctx) -> None:
    ctx = make_case_ctx()
    ok_step = _FakeStep()
    skip_step = _SkippedStep()
    fail_step = _FailingStep()
    workflow = _FakeWorkflow([ok_step, skip_step, fail_step])

    with mock.patch(
        "pywandahydra.postprocessing.workflows.base.resolve_workflow",
        return_value=workflow,
    ):
        result = run_postprocessing(ctx, workflow_name="fake", workflow_params={"foo": "bar"})

    assert list(result.items()) == [
        ("fake_step", True),
        ("skipped_step", True),
        ("failing_step", False),
    ]
