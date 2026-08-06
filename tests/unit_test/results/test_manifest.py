"""Tests for versioned run manifest persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pywandahydra.config.models import (
    ModelConfiguration,
    RunConfiguration,
)
from pywandahydra.results.manifest import (
    ManifestVersionError,
    RunManifest,
    SourceFile,
    read_manifest,
    sha256_file,
    write_manifest,
)
from pywandahydra.scenarios import AnalysisMeta
from pywandahydra.scenarios.models.document import ScenarioDocument


def _manifest(tmp_path: Path) -> RunManifest:
    source_path = tmp_path / "scenarios.xlsx"
    source_path.write_bytes(b"scenario source")
    configuration = RunConfiguration(
        run_id="run_001",
        output_root=tmp_path / "runs",
        scenario_file=source_path,
        model=ModelConfiguration(
            path=tmp_path / "model.wdi",
            wanda_bin=tmp_path / "wanda",
        ),
    )
    document = ScenarioDocument(
        analysis_metadata=AnalysisMeta(),
        scenarios=(),
        source_path=source_path,
    )
    return RunManifest.create(
        configuration=configuration,
        scenario_document=document,
        run_dir=tmp_path / "runs" / "run_001",
        sources=(SourceFile(name="scenarios.xlsx", sha256=sha256_file(source_path)),),
    )


def test_manifest_round_trip_is_atomic_and_preserves_source_hash(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)

    write_manifest(manifest)

    restored = read_manifest(manifest.run_dir)
    assert restored == manifest
    assert restored.sources[0].sha256 == sha256_file(tmp_path / "scenarios.xlsx")
    assert not (manifest.run_dir / "run_manifest.json.tmp").exists()


def test_manifest_rejects_unknown_schema_version(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    path = manifest.run_dir / "run_manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({**manifest.model_dump(mode="json"), "schema_version": 999}),
        encoding="utf-8",
    )

    with pytest.raises(ManifestVersionError, match="unsupported manifest schema version"):
        read_manifest(manifest.run_dir)
