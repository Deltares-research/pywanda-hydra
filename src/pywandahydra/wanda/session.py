"""WANDA model session context manager."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path

import pywanda

from ..config.models import ModelSpecification

logger = logging.getLogger(__name__)


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

    logger.debug(f"Creating WANDA model from: {path}")
    logger.debug(f"WANDA binary path: {wanda_bin}")

    try:
        logger.debug("Instantiating pywanda.WandaModel...")
        model = pywanda.WandaModel(str(path), wanda_bin)
        logger.debug("WandaModel created successfully")
    except Exception as e:
        logger.error(f"Failed to create WandaModel: {e}", exc_info=True)
        raise

    # Review version and upgrade if necessary
    try:
        logger.debug("Upgrading model if necessary...")
        model.upgrade_model()
        logger.debug("Model upgrade check completed")
    except Exception as e:
        logger.error(f"Failed to upgrade model: {e}", exc_info=True)
        try:
            model.close()
        except Exception as close_err:
            logger.warning(f"Error closing model after upgrade failure: {close_err}")
        raise

    try:
        yield model
    finally:
        logger.debug("Closing WANDA model session...")
        try:
            model.close()
            logger.debug("Model closed successfully")
        except Exception as e:
            logger.warning(f"Error closing WANDA model: {e}")
