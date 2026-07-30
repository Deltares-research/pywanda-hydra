"""Case-model file creation utilities."""

from __future__ import annotations

import shutil
import time
from pathlib import Path


def _unlink_stale_file(path: Path) -> None:
    """Remove a stale model artefact with small retry tolerance on Windows.

    WANDA can hold file handles briefly after session close; retries avoid
    turning these short-lived locks into deterministic setup failures.
    """
    for attempt in range(3):
        try:
            path.unlink()
            return
        except FileNotFoundError:
            # Another process removed the file between glob and unlink.
            return
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.1)


def prepare_scenario_model(
    base_model_path: Path,
    scenario_dir: str | Path,
    scenario_name: str,
) -> Path:
    """Create a scenario-specific copy of the base WANDA model files."""
    base_wdi = base_model_path
    if base_wdi.suffix.lower() != ".wdi":
        raise ValueError(f"Expected .wdi model path, got: {base_wdi}")

    scenario_dir = Path(scenario_dir)
    scenario_dir.mkdir(parents=True, exist_ok=True)

    target_wdi = scenario_dir / f"{base_wdi.stem}_{scenario_name}.wdi"
    target_wdx = target_wdi.with_suffix(".wdx")
    src_wdx = base_wdi.with_suffix(".wdx")

    for stale in scenario_dir.glob(f"{target_wdi.stem}.*"):
        try:
            _unlink_stale_file(stale)
        except OSError as e:
            raise RuntimeError(
                f"Cannot remove stale model file '{stale}' — it appears to be "
                "in use by another WANDA session. Close that session (or wait "
                "for the other run to finish) and retry."
            ) from e

    shutil.copyfile(base_wdi, target_wdi)
    if src_wdx.exists():
        shutil.copyfile(src_wdx, target_wdx)

    return target_wdi
