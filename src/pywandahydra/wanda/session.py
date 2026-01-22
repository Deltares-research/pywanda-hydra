"""WANDA model session context manager."""

from __future__ import annotations

from contextlib import contextmanager

import pywanda

from ..config.models import ModelSpecification


@contextmanager
def wanda_session(spec: ModelSpecification, *, model_path: str | None = None) -> pywanda.WandaModel:
    """Context manager for a WANDA model session.

    Parameters
    ----------
    spec : ModelSpecification
        The model specification containing model path and WANDA binary location.
    model_path : str | None, optional
        Optional override for the model path. If None, uses the path from spec.

    Yields
    ------
    pywanda.WandaModel
        An instance of the WANDA model.
    """
    path = model_path or spec.model_path
    model = pywanda.WandaModel(path, spec.wanda_bin)
    try:
        yield model
    finally:
        model.close()
