"""Integration test: E2E disuse through final case execution."""

from __future__ import annotations

import unittest
from pathlib import Path

import pytest

from pywandahydra.execution.case_execution import simulate_case
from pywandahydra.execution.plans import CasePlan, ModelSpecification
from pywandahydra.scenarios import ModelParameterChange, ScenarioSpecification
from pywandahydra.wanda.api import find_items_with_keyword, get_item
from pywandahydra.wanda.session import wanda_session


class TestDisusePSFullKeyword(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def _inject_fixtures(self, wanda_model_spec: ModelSpecification, tmp_path: Path) -> None:
        self.model_spec = wanda_model_spec
        self.tmp_path = tmp_path

    def _scenario(self, *, disused: bool) -> ScenarioSpecification:
        return ScenarioSpecification(
            number=1,
            include=True,
            name="disuse_test",
            parameter_changes=[
                ModelParameterChange(component="PSFull", property="disuse", value=disused)
            ],
        )

    def _scenario_model_path(self, case_dir: Path) -> Path:
        stem = self.model_spec.model_path.stem
        return case_dir / f"{stem}_disuse_test.wdi"

    def _assert_psfull_disused(self, model, *, disused: bool) -> None:
        items = find_items_with_keyword(model, "PSFull")
        self.assertGreater(len(items), 0, "PSFull keyword matched no items")
        types_present = {ref.type for ref in items}
        self.assertGreater(len(types_present), 1, "Expected mixed item types from PSFull")
        for ref in items:
            item = get_item(model, ref)
            self.assertEqual(item.is_disused(), disused, f"{ref.name} disuse mismatch")

    def test_psfull_disuse_via_case_execution_save_and_reset(self) -> None:
        case_dir = self.tmp_path / "run" / "scenarios" / "disuse_test"

        # --- Phase 1: Disuse ---
        result = simulate_case(
            CasePlan(
                case_id="disuse_test",
                case_dir=case_dir,
                model_spec=self.model_spec,
                scenario=self._scenario(disused=True),
            )
        )
        self.assertTrue(result.success)

        model_path = self._scenario_model_path(case_dir)
        with wanda_session(spec=self.model_spec, model_path=model_path) as model:
            self._assert_psfull_disused(model, disused=True)

        # --- Phase 2: Reset ---
        result = simulate_case(
            CasePlan(
                case_id="disuse_test",
                case_dir=case_dir,
                model_spec=self.model_spec,
                scenario=self._scenario(disused=False),
            )
        )
        self.assertTrue(result.success)

        with wanda_session(spec=self.model_spec, model_path=model_path) as model:
            self._assert_psfull_disused(model, disused=False)
