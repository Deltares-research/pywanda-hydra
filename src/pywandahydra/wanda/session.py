"""WANDA model session context manager."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pywanda

from ..config.models import ModelSpecification


@contextmanager
def wanda_session(
    spec: ModelSpecification,
    *,
    model_path: Path | None = None,
) -> pywanda.WandaModel:
    """Context manager for a WANDA model session.

    Parameters
    ----------
    spec : ModelSpecification
        The model specification containing model path and WANDA binary location.
    model_path : Path | None, optional
        Optional override for the model path. If None, uses the path from spec.

    Yields
    ------
    pywanda.WandaModel
        An instance of the WANDA model.
    """
    path = model_path or spec.model_path
    wanda_bin = str(spec.wanda_bin)
    if not wanda_bin.endswith("\\\\"):
        wanda_bin += "\\\\"
    model = pywanda.WandaModel(str(path), wanda_bin)

    # Review version and upgrade if necessary
    model.upgrade_model()

    try:
        yield model
    finally:
        model.close()
