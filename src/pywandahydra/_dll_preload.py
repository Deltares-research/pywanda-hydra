"""Preload the system MSVC runtime before third-party wheels can shadow it.

Some wheels (notably pyarrow) bundle their own ``msvcp140.dll``. Windows maps
a DLL by base name only once per process, so whichever copy loads first wins
process-wide. pyarrow's bundled copy (14.28, from 2020) is older than what the
WANDA native DLLs were built against; if pandas/pyarrow import before pywanda
opens a model, ``pywanda.WandaModel`` dereferences missing runtime state and
the process dies with an access violation (0xC0000005) — no Python traceback.

Loading the up-to-date system runtime here, before any heavy imports, makes
every later resolver bind to it instead.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_RUNTIME_DLLS = ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")


def preload_msvc_runtime() -> None:
    """Load the system MSVC runtime DLLs into the process (Windows only).

    Best effort: a missing DLL or non-Windows platform is silently skipped.
    Must run before pandas/pyarrow are imported to have any effect.
    """
    if sys.platform != "win32":
        return

    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    for name in _RUNTIME_DLLS:
        dll_path = system32 / name
        if not dll_path.is_file():
            continue
        try:
            ctypes.WinDLL(str(dll_path))
            logger.debug("Preloaded %s", dll_path)
        except OSError as exc:
            logger.debug("Could not preload %s: %s", dll_path, exc)
