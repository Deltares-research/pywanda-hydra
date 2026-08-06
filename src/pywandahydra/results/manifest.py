"""Versioned, atomic run provenance manifests."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from ..config.models import RunConfiguration
from ..scenarios.models.document import ScenarioDocument

MANIFEST_FILENAME = "run_manifest.json"
_SCHEMA_VERSION = 1


class ManifestError(ValueError):
    """Base error for invalid or unreadable run manifests."""


class ManifestVersionError(ManifestError):
    """Raised when a manifest uses a schema version this package cannot read."""


class ManifestCorruptionError(ManifestError):
    """Raised when a manifest is absent, malformed, or fails validation."""


class SourceFile(BaseModel):
    """Identity and hash of an authored input captured for a run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    sha256: str


class RuntimeInfo(BaseModel):
    """Versions available while the manifest was created."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    package_version: str
    python_version: str
    pywanda_version: str | None = None
    wanda_version: str | None = None


class RunManifest(BaseModel):
    """The sole machine-readable source of run provenance and offline inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    directory_schema_version: Literal[1] = 1
    configuration: RunConfiguration
    scenario_document: ScenarioDocument
    run_dir: Path
    created_at: str
    invocation: tuple[str, ...] = ()
    runtime: RuntimeInfo
    sources: tuple[SourceFile, ...]

    @classmethod
    def create(
        cls,
        *,
        configuration: RunConfiguration,
        scenario_document: ScenarioDocument,
        run_dir: Path,
        sources: tuple[SourceFile, ...],
    ) -> RunManifest:
        """Build a v1 manifest using only import-safe runtime provenance."""
        return cls(
            configuration=configuration,
            scenario_document=scenario_document,
            run_dir=run_dir,
            created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            invocation=tuple(sys.argv),
            runtime=RuntimeInfo(
                package_version=_package_version("pywanda-hydra"),
                python_version=platform.python_version(),
                pywanda_version=_optional_package_version("pywanda"),
            ),
            sources=sources,
        )


def manifest_path(run_dir: Path) -> Path:
    """Return the canonical manifest path for a run directory."""
    return run_dir / MANIFEST_FILENAME


def sha256_file(path: Path) -> str:
    """Calculate a stable SHA-256 digest for an authored input file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def write_manifest(manifest: RunManifest) -> Path:
    """Atomically persist ``manifest`` as the run's sole metadata document."""
    path = manifest_path(manifest.run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                manifest.model_dump(mode="json"), stream, sort_keys=True, separators=(",", ":")
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    return path


def read_manifest(run_dir: Path) -> RunManifest:
    """Read and validate a v1 manifest, rejecting unknown future versions."""
    path = manifest_path(run_dir)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestCorruptionError(f"Missing run manifest: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestCorruptionError(f"Corrupt run manifest at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestCorruptionError(f"Corrupt run manifest at {path}: root must be an object")
    if value.get("schema_version") != _SCHEMA_VERSION:
        raise ManifestVersionError(
            f"unsupported manifest schema version {value.get('schema_version')!r} at {path}"
        )
    try:
        return RunManifest.model_validate(value)
    except ValidationError as exc:
        raise ManifestCorruptionError(f"Corrupt run manifest at {path}: {exc}") from exc


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unknown"


def _optional_package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None
