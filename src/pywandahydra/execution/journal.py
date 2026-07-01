"""Per-case journal — atomic state file + append-only event log.

Provides concurrency-safe status tracking for each scenario case,
enabling resume, dashboards, and aggregated reporting.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from filelock import FileLock


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# State model
# ---------------------------------------------------------------------------


@dataclass
class CaseState:
    """Current status of a single case. Persisted as state.json.

    Attributes:
        schema_version: Schema version for forward compatibility.
        case_id: Unique case identifier.
        status: Current execution status.
        postprocess_status: Current post-processing status.
        created_at: ISO timestamp when the case was created.
        queued_at: ISO timestamp when queued for execution.
        started_at: ISO timestamp when execution started.
        finished_at: ISO timestamp when execution finished.
        duration_s: Duration of the execution in seconds.
        worker_pid: PID of the worker process.
        host: Hostname of the executing machine.
        attempt: Current attempt number.
        error: Error message if failed.
        config_hash: Hash of the case plan configuration.
        artefacts: Paths to generated artefacts (relative to case_dir).
    """

    schema_version: int = 1
    case_id: str = ""
    status: str = "CREATED"
    postprocess_status: str = "PENDING"
    created_at: str = field(default_factory=_now_iso)
    queued_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_s: float | None = None
    worker_pid: int | None = None
    host: str = field(default_factory=socket.gethostname)
    attempt: int = 1
    error: str | None = None
    config_hash: str = ""
    artefacts: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Journal class
# ---------------------------------------------------------------------------


class CaseJournal:
    """Per-case status file (atomic write) + append-only JSONL event log.

    File layout in case_dir::

        state.json      — current status (overwritten atomically)
        events.jsonl    — append-only event log
        case.lock       — filelock for mutual exclusion

    Args:
        case_dir: Path to the case directory.
    """

    def __init__(self, case_dir: Path) -> None:
        case_dir.mkdir(parents=True, exist_ok=True)
        self.dir = case_dir
        self.state_path = case_dir / "state.json"
        self.events_path = case_dir / "events.jsonl"
        self._lock = FileLock(case_dir / "case.lock", timeout=10)

    # ---- Locking ---------------------------------------------------------

    def acquire(self) -> None:
        """Acquire the case lock (blocking, with timeout).

        Raises:
            filelock.Timeout: If lock cannot be acquired within timeout.
        """
        self._lock.acquire()

    def release(self) -> None:
        """Release the case lock."""
        self._lock.release()

    def __enter__(self) -> CaseJournal:
        self.acquire()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.release()

    # ---- State -----------------------------------------------------------

    def read_state(self) -> CaseState | None:
        """Read the current state from state.json.

        Returns:
            CaseState if the file exists, None otherwise.
        """
        if not self.state_path.exists():
            return None
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return CaseState(**data)
        except (json.JSONDecodeError, TypeError):
            return None

    def write_state(self, state: CaseState) -> None:
        """Write state atomically via temp file + os.replace.

        Args:
            state: The CaseState to persist.
        """
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(asdict(state), indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        os.replace(tmp, self.state_path)

    # ---- Events ----------------------------------------------------------

    def event(self, name: str, **fields: Any) -> None:
        """Append an event to the JSONL log.

        Each event is a single JSON line. Append writes of <= 4 KiB are
        atomic on both NTFS and POSIX.

        Args:
            name: Event name (e.g. "started", "succeeded", "failed").
            **fields: Additional event fields.
        """
        line = json.dumps({"ts": _now_iso(), "evt": name, **fields}, default=str) + "\n"
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(line)

    # ---- Transitions -----------------------------------------------------

    def transition(self, status: str, **patch: Any) -> CaseState:
        """Transition the case to a new status.

        Reads current state (or creates default), applies status + patch,
        writes atomically, and appends an event.

        Args:
            status: New status string.
            **patch: Additional fields to update on the state.

        Returns:
            The updated CaseState.
        """
        state = self.read_state() or CaseState(case_id=self.dir.name)
        state.status = status
        for key, value in patch.items():
            if hasattr(state, key):
                setattr(state, key, value)
        self.write_state(state)
        self.event(status.lower(), **{k: v for k, v in patch.items() if k != "artefacts"})
        return state

    # ---- Convenience helpers ---------------------------------------------

    def is_completed(self, config_hash: str) -> bool:
        """Check if this case already completed with matching config.

        Args:
            config_hash: Expected config hash for idempotency.

        Returns:
            True if the case succeeded with the same config_hash.
        """
        state = self.read_state()
        if state is None:
            return False
        return state.status == "SUCCEEDED" and state.config_hash == config_hash

    def needs_postprocessing(self) -> bool:
        """Check if this case needs post-processing.

        Returns:
            True if status is SUCCEEDED but postprocess_status is not DONE.
        """
        state = self.read_state()
        if state is None:
            return False
        return state.status == "SUCCEEDED" and state.postprocess_status != "DONE"


def resume_decision(
    *,
    journal: CaseJournal,
    config_hash: str,
    reuse_existing_data: bool,
) -> Literal["skip", "rerun", "run"]:
    """Determine resume behavior for a case.

    Args:
        journal: Case journal used to inspect completion state.
        config_hash: Expected config hash for idempotency checks.
        reuse_existing_data: Whether a completed run should be reused (skipped) rather than re-run.

    Returns:
        "skip" if case should be skipped in resume mode,
        "rerun" if case completed but must be re-run,
        "run" if case has not completed for this config.
    """
    completed = journal.is_completed(config_hash)
    if completed and reuse_existing_data:
        return "skip"
    if completed and not reuse_existing_data:
        return "rerun"
    return "run"
