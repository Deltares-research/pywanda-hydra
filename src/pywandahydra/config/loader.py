"""Load authored run configuration files."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import RunConfiguration


def load_run_config(path: Path | str) -> RunConfiguration:
    """Load and validate a run configuration from a YAML or JSON file.

    Args:
        path: Path to the configuration file (.yaml, .yml, or .json).

    Returns:
        Validated RunConfig instance.

    Raises:
        ValueError: If the file format is unsupported or validation fails.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    ext = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if ext in (".yaml", ".yml"):
        raw = yaml.safe_load(text)
    elif ext == ".json":
        raw = json.loads(text)
    else:
        raise ValueError(f"Unsupported config format: '{ext}'. Use .yaml, .yml, or .json.")
    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a mapping, got: {type(raw).__name__}")
    try:
        return RunConfiguration.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid run configuration in {path}:\n{exc}") from None
