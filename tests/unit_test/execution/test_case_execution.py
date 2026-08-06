"""Unit tests for one-case execution using the WANDA access protocol mock."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, create_autospec, patch

from pywandahydra.execution.case_execution import simulate_case
from pywandahydra.execution.plans import CasePlan, ModelSpecification
from pywandahydra.scenarios import ScenarioSpecification
from pywandahydra.wanda.model_access import WandaModelAccess


def _plan(tmp_path: Path) -> CasePlan:
    model_path = tmp_path / "model.wdi"
    model_path.write_bytes(b"model")
    return CasePlan(
        case_id="case_one",
        case_dir=tmp_path / "case_one",
        model_spec=ModelSpecification(model_path=model_path, wanda_bin=tmp_path),
        scenario=ScenarioSpecification(number=1, include=True, name="case_one"),
    )


def _access_mock(model_path: Path) -> tuple[MagicMock, MagicMock]:
    """Create a protocol-checked access mock with a managed model session."""
    access = create_autospec(WandaModelAccess, instance=True)
    model = MagicMock(name="wanda_model")
    access.prepare_scenario_model.return_value = model_path
    access.session.return_value.__enter__.return_value = model
    return access, model


def test_simulate_case_uses_protocol_access_and_commits_results(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    access, model = _access_mock(plan.case_dir / "model" / "model_case_one.wdi")
    extracted = MagicMock(name="extracted_simulation_data")

    with (
        patch("pywandahydra.execution.case_execution._model_access", return_value=access),
        patch(
            "pywandahydra.execution.case_execution.extract_simulation_data",
            return_value=extracted,
        ) as extract,
        patch("pywandahydra.execution.case_execution.ParquetResultStore.write") as write,
    ):
        result = simulate_case(plan)

    assert result.success
    assert result.action == "simulate"
    access.prepare_scenario_model.assert_called_once_with(
        plan.model_spec.model_path,
        plan.case_dir,
        plan.scenario.name,
    )
    access.session.assert_called_once_with(
        plan.model_spec,
        plan.case_dir / "model" / "model_case_one.wdi",
    )
    access.save_input.assert_called_once_with(model)
    extract.assert_called_once()
    write.assert_called_once()