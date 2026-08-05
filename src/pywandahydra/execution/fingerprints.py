"""Canonical fingerprints for simulation inputs and output reductions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_SIMULATION_FINGERPRINT_SCHEMA_VERSION = 1
_OUTPUT_FINGERPRINT_SCHEMA_VERSION = 1


def simulation_fingerprint(
    *,
    model_path: Path,
    upgrade: bool,
    wanda_version: str | None,
    pywanda_version: str | None,
    run_steady: bool,
    run_unsteady: bool,
    parameter_changes: Sequence[Mapping[str, Any]],
) -> str:
    """Hash exactly the inputs that can alter WANDA's raw results."""
    companion_path = model_path.with_suffix(".wdx")
    return _fingerprint(
        {
            "schema_version": _SIMULATION_FINGERPRINT_SCHEMA_VERSION,
            "model": {
                "wdi_sha256": _file_hash(model_path),
                "wdx_sha256": _file_hash(companion_path) if companion_path.is_file() else None,
            },
            "upgrade": upgrade,
            "wanda_version": wanda_version,
            "pywanda_version": pywanda_version,
            "steady": run_steady,
            "unsteady": run_unsteady,
            "parameter_changes": list(parameter_changes),
        }
    )


def output_fingerprint(
    *,
    post_processing: Mapping[str, Any],
    theme: str | None,
    table_formats: Sequence[str],
    figure_formats: Sequence[str],
) -> str:
    """Hash output configuration without including case identity or paths."""
    return _fingerprint(
        {
            "schema_version": _OUTPUT_FINGERPRINT_SCHEMA_VERSION,
            "post_processing": post_processing,
            "theme": theme,
            "table_formats": list(table_formats),
            "figure_formats": list(figure_formats),
        }
    )


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
