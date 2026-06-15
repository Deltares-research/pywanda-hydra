"""Unit tests for postprocessing.core.pipeline.run_postprocessing."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import ClassVar
from unittest import mock

from pywandahydra.postprocessing.core.context import CaseContext
from pywandahydra.postprocessing.core.pipeline import run_postprocessing
from pywandahydra.postprocessing.io.cache import ParquetCache
from pywandahydra.scenarios.schema import ScenarioMeta, ScenarioSpecification


def _make_ctx(tmp_path: Path) -> CaseContext:
    return CaseContext(
        cache=ParquetCache(tmp_path),
        scenario=ScenarioSpecification(
            meta=ScenarioMeta.model_validate(
                {"Number": 1, "Include": True, "Name": "case_001"}
            )
        ),
        case_dir=tmp_path,
    )


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


class TestRunPostprocessing(unittest.TestCase):
    def test_step_runs_successfully(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir))
            step = _FakeStep()
            workflow = _FakeWorkflow([step])

            with mock.patch(
                "pywandahydra.postprocessing.workflows.base.resolve_workflow",
                return_value=workflow,
            ):
                result = run_postprocessing(ctx, workflow_name="fake")

            self.assertEqual(result, {"fake_step": True})
            self.assertTrue(step.run_called)

    def test_step_skipped_when_not_applicable(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir))
            step = _SkippedStep()
            workflow = _FakeWorkflow([step])

            with mock.patch(
                "pywandahydra.postprocessing.workflows.base.resolve_workflow",
                return_value=workflow,
            ):
                result = run_postprocessing(ctx, workflow_name="fake")

            self.assertEqual(result, {"skipped_step": True})
            self.assertFalse(step.run_called)

    def test_step_exception_recorded_as_failure(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir))
            step = _FailingStep()
            workflow = _FakeWorkflow([step])

            with mock.patch(
                "pywandahydra.postprocessing.workflows.base.resolve_workflow",
                return_value=workflow,
            ):
                result = run_postprocessing(ctx, workflow_name="fake")

            self.assertEqual(result, {"failing_step": False})
            self.assertTrue(step.run_called)

    def test_multiple_steps_result_dict_ordering(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            ctx = _make_ctx(Path(tmp_dir))
            ok_step = _FakeStep()
            skip_step = _SkippedStep()
            fail_step = _FailingStep()
            workflow = _FakeWorkflow([ok_step, skip_step, fail_step])

            with mock.patch(
                "pywandahydra.postprocessing.workflows.base.resolve_workflow",
                return_value=workflow,
            ):
                result = run_postprocessing(
                    ctx, workflow_name="fake", workflow_params={"foo": "bar"}
                )

            self.assertEqual(
                list(result.items()),
                [
                    ("fake_step", True),
                    ("skipped_step", True),
                    ("failing_step", False),
                ],
            )


if __name__ == "__main__":
    unittest.main()
