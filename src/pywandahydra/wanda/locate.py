"""Locate the WANDA installation on the current machine."""

from __future__ import annotations

import os
import re
from pathlib import Path

WANDA_BIN_ENV_VAR = "PYWANDAHYDRA_WANDA_BIN"

_SEARCH_ROOTS = (
    Path(r"C:\Program Files (x86)\Deltares"),
    Path(r"C:\Program Files\Deltares"),
)


def _is_wanda_bin(path: Path) -> bool:
    """Return whether a directory is a usable WANDA bin directory."""
    return (path / "Wandadef.dat").is_file()


def _version_key(install_name: str) -> tuple[int, ...]:
    """Sortable version tuple from an install dir name like 'Wanda 4.8'."""
    return tuple(int(part) for part in re.findall(r"\d+", install_name))


def find_wanda_bin() -> Path:
    """Resolve the WANDA binary directory for this machine.

    Resolution order:

    1. The ``PYWANDAHYDRA_WANDA_BIN`` environment variable, if set.
    2. The newest ``Wanda *`` installation under Program Files,
       preferring ``Bin64`` over ``Bin``.

    A directory only qualifies if it contains ``Wandadef.dat`` — passing
    anything else to ``pywanda.WandaModel`` fails (or crashes the process
    with an access violation when other native libraries are loaded).

    Returns
    -------
    Path
        The validated WANDA bin directory.

    Raises
    ------
    FileNotFoundError
        If the environment variable points to an invalid directory, or no
        WANDA installation can be discovered.
    """
    env_value = os.environ.get(WANDA_BIN_ENV_VAR)
    if env_value:
        path = Path(env_value)
        if not _is_wanda_bin(path):
            raise FileNotFoundError(
                f"{WANDA_BIN_ENV_VAR}={env_value!r} is not a valid WANDA bin "
                "directory (Wandadef.dat not found)"
            )
        return path

    candidates: list[tuple[tuple[int, ...], int, Path]] = []
    for root in _SEARCH_ROOTS:
        if not root.is_dir():
            continue
        for install in root.glob("Wanda *"):
            for preference, bin_name in enumerate(("Bin", "Bin64")):
                bin_dir = install / bin_name
                if _is_wanda_bin(bin_dir):
                    candidates.append((_version_key(install.name), preference, bin_dir))

    if not candidates:
        raise FileNotFoundError(
            "No WANDA installation found under "
            + " or ".join(str(root) for root in _SEARCH_ROOTS)
            + f". Install WANDA or set {WANDA_BIN_ENV_VAR} to the bin directory."
        )

    return max(candidates)[2]
