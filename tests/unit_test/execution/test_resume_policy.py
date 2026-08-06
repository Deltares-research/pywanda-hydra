from __future__ import annotations

import pytest

from pywandahydra.execution.run_directory import recovery_decision
from pywandahydra.execution.status import CaseStatus
from pywandahydra.results import ComponentIdentity, DataRequirements, ResultInventory


@pytest.mark.parametrize(
    (
        "status",
        "simulation_fingerprint",
        "complete",
        "inventory",
        "requirements",
        "outputs_current",
        "expected",
    ),
    [
        (None, "simulation", True, ResultInventory(), DataRequirements(), True, "simulate"),
        (
            CaseStatus(case_id="case", simulation_status="failed"),
            "simulation",
            True,
            ResultInventory(),
            DataRequirements(),
            True,
            "simulate",
        ),
        (
            CaseStatus(case_id="case", simulation_status="succeeded", simulation_fingerprint="old"),
            "simulation",
            True,
            ResultInventory(),
            DataRequirements(),
            True,
            "simulate",
        ),
        (
            CaseStatus(
                case_id="case",
                simulation_status="succeeded",
                simulation_fingerprint="simulation",
            ),
            "simulation",
            False,
            None,
            DataRequirements(),
            True,
            "simulate",
        ),
        (
            CaseStatus(
                case_id="case",
                simulation_status="succeeded",
                simulation_fingerprint="simulation",
                postprocessing_status="failed",
            ),
            "simulation",
            True,
            ResultInventory(),
            DataRequirements(),
            True,
            "postprocess",
        ),
        (
            CaseStatus(
                case_id="case",
                simulation_status="succeeded",
                simulation_fingerprint="simulation",
                postprocessing_status="succeeded",
                output_fingerprint="old",
            ),
            "simulation",
            True,
            ResultInventory(),
            DataRequirements(),
            True,
            "postprocess",
        ),
        (
            CaseStatus(
                case_id="case",
                simulation_status="succeeded",
                simulation_fingerprint="simulation",
                postprocessing_status="succeeded",
                output_fingerprint="output",
            ),
            "simulation",
            True,
            ResultInventory(),
            DataRequirements(),
            False,
            "postprocess",
        ),
        (
            CaseStatus(
                case_id="case",
                simulation_status="succeeded",
                simulation_fingerprint="simulation",
                postprocessing_status="succeeded",
                output_fingerprint="output",
            ),
            "simulation",
            True,
            ResultInventory(),
            DataRequirements(),
            True,
            "skip",
        ),
    ],
)
def test_recovery_decision_matrix(
    status: CaseStatus | None,
    simulation_fingerprint: str,
    complete: bool,
    inventory: ResultInventory | None,
    requirements: DataRequirements,
    outputs_current: bool,
    expected: str,
) -> None:
    assert (
        recovery_decision(
            status=status,
            simulation_fingerprint=simulation_fingerprint,
            output_fingerprint="output",
            result_store_complete=complete,
            inventory=inventory,
            requirements=requirements,
            outputs_current=outputs_current,
        )
        == expected
    )


def test_recovery_simulates_when_inventory_is_insufficient() -> None:
    status = CaseStatus(
        case_id="case",
        simulation_status="succeeded",
        simulation_fingerprint="simulation",
        postprocessing_status="succeeded",
        output_fingerprint="output",
    )
    requirements = DataRequirements(components=frozenset({ComponentIdentity("pipe", "pressure")}))

    assert (
        recovery_decision(
            status=status,
            simulation_fingerprint="simulation",
            output_fingerprint="output",
            result_store_complete=True,
            inventory=ResultInventory(),
            requirements=requirements,
            outputs_current=True,
        )
        == "simulate"
    )
