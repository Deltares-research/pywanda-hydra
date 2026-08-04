from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pywandahydra.execution.status import CaseStatus, CaseStatusStore, StatusCorruptionError


def test_status_store_replaces_status_atomically(tmp_path: Path) -> None:
    store = CaseStatusStore(tmp_path)

    with patch(
        "pywandahydra.execution.status.os.replace", wraps=os.replace
    ) as replace:
        store.write(CaseStatus(case_id="case_001", simulation_status="succeeded"))

    assert replace.call_count == 1
    assert store.read() == CaseStatus(case_id="case_001", simulation_status="succeeded")
    assert not (tmp_path / "status.json.tmp").exists()


@pytest.mark.parametrize(
    "contents",
    [
        "{not json",
        json.dumps({"schema_version": 1, "case_id": "case_001"}),
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "case_001",
                "simulation_status": "unknown",
                "postprocessing_status": "pending",
                "postprocessing_outcomes": [],
                "generated_paths": [],
            }
        ),
    ],
)
def test_status_store_rejects_corrupt_existing_status(tmp_path: Path, contents: str) -> None:
    (tmp_path / "status.json").write_text(contents, encoding="utf-8")

    with pytest.raises(StatusCorruptionError):
        CaseStatusStore(tmp_path).read()


def test_status_store_rejects_unsupported_schema(tmp_path: Path) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps({"schema_version": 2}), encoding="utf-8"
    )

    with pytest.raises(StatusCorruptionError, match="unsupported schema"):
        CaseStatusStore(tmp_path).read()
