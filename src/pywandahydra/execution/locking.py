"""Fail-fast local filesystem locks and one-writer case logging."""

from __future__ import annotations

import json
import logging
import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout


class LockContentionError(RuntimeError):
    """Base error for a lock held by another active process."""

    def __init__(self, path: Path, owner: dict[str, object] | None) -> None:
        self.path = path
        self.owner = owner
        owner_detail = f"; owner metadata: {owner}" if owner else ""
        super().__init__(f"Lock is already held: {path}{owner_detail}")


class RunLockedError(LockContentionError):
    """Raised when another invocation holds a run lock."""


class CaseLockedError(LockContentionError):
    """Raised when another worker holds a case lock."""


class _LocalLock:
    error_type: type[LockContentionError]

    def __init__(self, path: Path) -> None:
        self.path = path
        self.owner_path = path.with_name(f"{path.name}.owner.json")
        self._lock = FileLock(path, timeout=0)

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._lock.acquire()
        except Timeout as exc:
            raise self.error_type(self.path, _read_owner(self.owner_path)) from exc
        self.owner_path.write_text(
            json.dumps({"pid": os.getpid(), "hostname": socket.gethostname()}, sort_keys=True),
            encoding="utf-8",
        )

    def release(self) -> None:
        self._lock.release()

    def __enter__(self) -> _LocalLock:
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


class RunLock(_LocalLock):
    """Exclusive lock for the lifecycle of one run invocation."""

    error_type = RunLockedError

    def __init__(self, run_dir: Path) -> None:
        super().__init__(run_dir / ".run.lock")


class CaseLock(_LocalLock):
    """Defensive exclusive lock for work within one case directory."""

    error_type = CaseLockedError

    def __init__(self, case_dir: Path) -> None:
        super().__init__(case_dir / ".case.lock")


def _read_owner(path: Path) -> dict[str, object] | None:
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


@contextmanager
def case_log_handler(case_dir: Path) -> Iterator[logging.Handler]:
    """Attach one local file writer while the caller holds ``CaseLock``."""
    handler = logging.FileHandler(case_dir / "case.log", encoding="utf-8")
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    try:
        yield handler
    finally:
        root_logger.removeHandler(handler)
        handler.close()
