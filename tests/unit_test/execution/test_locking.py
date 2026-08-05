from __future__ import annotations

from pathlib import Path

import pytest

from pywandahydra.execution.locking import CaseLock, CaseLockedError, RunLock, RunLockedError


def test_case_lock_fails_immediately_when_already_held(tmp_path: Path) -> None:
    with CaseLock(tmp_path):
        with pytest.raises(CaseLockedError) as error:
            CaseLock(tmp_path).acquire()

    assert error.value.path == tmp_path / ".case.lock"
    assert error.value.owner is not None


def test_run_lock_fails_immediately_when_already_held(tmp_path: Path) -> None:
    with RunLock(tmp_path):
        with pytest.raises(RunLockedError):
            RunLock(tmp_path).acquire()
