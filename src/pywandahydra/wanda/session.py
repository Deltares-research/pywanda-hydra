"""WANDA model session context manager."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path

import pywanda

from ..execution.plans import ModelSpecification

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
    if not wanda_bin.endswith("\\"):
        wanda_bin += "\\"

    logger.debug("Creating WANDA model from: %s", path)
    logger.debug("WANDA binary path: %s", wanda_bin)

    try:
        logger.debug("Instantiating pywanda.WandaModel...")
        model = pywanda.WandaModel(str(path), wanda_bin)
        logger.debug("WandaModel created successfully")
    except Exception:
        logger.error("Failed to create WandaModel", exc_info=True)
        raise

    # Upgrade only when explicitly requested: upgrade_model() rewrites the
    # model files natively and is unnecessary churn for models already at
    # the installed WANDA version.
    if spec.upgrade:
        try:
            logger.debug("Upgrading model if necessary...")
            model.upgrade_model()
            logger.debug("Model upgrade check completed")
        except Exception:
            logger.error("Failed to upgrade model", exc_info=True)
            try:
                model.close()
            except Exception:
                logger.warning("Error closing model after upgrade failure", exc_info=True)
            raise

    try:
        logger.debug("Yielding WANDA model for session...")
        yield model
    finally:
        logger.debug("Closing WANDA model session...")
        try:
            model.close()
            logger.debug("Model closed successfully")
        except Exception:
            logger.warning("Error closing WANDA model", exc_info=True)
