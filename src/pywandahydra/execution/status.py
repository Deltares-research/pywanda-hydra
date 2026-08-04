"""Typed, atomic persistence for a case's current execution status."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

SimulationStatus = Literal["pending", "running", "succeeded", "failed"]
PostProcessingStatus = Literal[
    "pending", "running", "succeeded", "failed", "not_required"
]

_SCHEMA_VERSION = 1
_SIMULATION_STATUSES = frozenset({"pending", "running", "succeeded", "failed"})
_POSTPROCESSING_STATUSES = frozenset(
    {"pending", "running", "succeeded", "failed", "not_required"}
)


class StatusCorruptionError(ValueError):
    """Raised when an existing status file cannot be trusted."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Corrupt case status at {path}: {reason}")


@dataclass(frozen=True)
class SerializedPostProcessingOutcome:
    """Durable representation of one post-processing routine outcome."""

    routine_name: str
    status: Literal["succeeded", "skipped", "failed"]
    skip_reason: str | None = None
    error: str | None = None
    created_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class CaseStatus:
    """The complete current state for one case, persisted as ``status.json``."""

    case_id: str
    simulation_status: SimulationStatus = "pending"
    postprocessing_status: PostProcessingStatus = "pending"
    simulation_fingerprint: str | None = None
    output_fingerprint: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_s: float | None = None
    error_summary: str | None = None
    postprocessing_outcomes: tuple[SerializedPostProcessingOutcome, ...] = ()
    generated_paths: tuple[str, ...] = ()
    schema_version: int = field(default=_SCHEMA_VERSION, init=False)


class CaseStatusStore:
    """Read and atomically replace one case status; callers own locking."""

    def __init__(self, case_dir: Path) -> None:
        self.case_dir = case_dir
        self.path = case_dir / "status.json"

    def read(self) -> CaseStatus | None:
        """Return persisted status, or ``None`` only when it is absent."""
        if not self.path.exists():
            return None
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StatusCorruptionError(self.path, str(exc)) from exc
        return _status_from_json(value, self.path)

    def write(self, status: CaseStatus) -> None:
        """Durably replace ``status.json`` using a sibling temporary file."""
        self.case_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".json.tmp")
        value = _status_to_json(status)
        try:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(value, stream, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self.path)
        except OSError:
            temporary_path.unlink(missing_ok=True)
            raise


def _status_to_json(status: CaseStatus) -> dict[str, Any]:
    value = asdict(status)
    value["postprocessing_outcomes"] = [
        {
            **asdict(outcome),
            "created_paths": list(outcome.created_paths),
        }
        for outcome in status.postprocessing_outcomes
    ]
    value["generated_paths"] = list(status.generated_paths)
    return value


def _status_from_json(value: object, path: Path) -> CaseStatus:
    if not isinstance(value, dict):
        raise StatusCorruptionError(path, "status root must be a JSON object")
    schema_version = value.get("schema_version")
    if schema_version != _SCHEMA_VERSION:
        raise StatusCorruptionError(path, f"unsupported schema version {schema_version!r}")
    try:
        case_id = _string(value, "case_id")
        simulation_status = _status(value, "simulation_status", _SIMULATION_STATUSES)
        postprocessing_status = _status(
            value, "postprocessing_status", _POSTPROCESSING_STATUSES
        )
        duration_s = _optional_number(value, "duration_s")
        outcomes = tuple(_outcome(item) for item in _list(value, "postprocessing_outcomes"))
        return CaseStatus(
            case_id=case_id,
            simulation_status=cast(SimulationStatus, simulation_status),
            postprocessing_status=cast(PostProcessingStatus, postprocessing_status),
            simulation_fingerprint=_optional_string(value, "simulation_fingerprint"),
            output_fingerprint=_optional_string(value, "output_fingerprint"),
            started_at=_optional_string(value, "started_at"),
            finished_at=_optional_string(value, "finished_at"),
            duration_s=duration_s,
            error_summary=_optional_string(value, "error_summary"),
            postprocessing_outcomes=outcomes,
            generated_paths=tuple(_string_list(value, "generated_paths")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise StatusCorruptionError(path, str(exc)) from exc


def _string(value: dict[str, object], name: str) -> str:
    item = value[name]
    if not isinstance(item, str) or not item:
        raise ValueError(f"{name} must be a non-empty string")
    return item


def _optional_string(value: dict[str, object], name: str) -> str | None:
    item = value.get(name)
    if item is not None and not isinstance(item, str):
        raise ValueError(f"{name} must be a string or null")
    return item


def _optional_number(value: dict[str, object], name: str) -> float | None:
    item = value.get(name)
    if item is None:
        return None
    if isinstance(item, bool) or not isinstance(item, int | float):
        raise ValueError(f"{name} must be a number or null")
    return float(item)


def _status(value: dict[str, object], name: str, allowed: frozenset[str]) -> str:
    item = _string(value, name)
    if item not in allowed:
        raise ValueError(f"{name} has unsupported value {item!r}")
    return item


def _list(value: dict[str, object], name: str) -> list[object]:
    item = value.get(name)
    if not isinstance(item, list):
        raise ValueError(f"{name} must be a list")
    return item


def _string_list(value: dict[str, object], name: str) -> list[str]:
    items = _list(value, name)
    if not all(isinstance(item, str) for item in items):
        raise ValueError(f"{name} must contain only strings")
    return [cast(str, item) for item in items]


def _outcome(value: object) -> SerializedPostProcessingOutcome:
    if not isinstance(value, dict):
        raise ValueError("postprocessing outcome must be an object")
    status = _string(value, "status")
    if status not in {"succeeded", "skipped", "failed"}:
        raise ValueError(f"postprocessing outcome has unsupported status {status!r}")
    return SerializedPostProcessingOutcome(
        routine_name=_string(value, "routine_name"),
        status=cast(Literal["succeeded", "skipped", "failed"], status),
        skip_reason=_optional_string(value, "skip_reason"),
        error=_optional_string(value, "error"),
        created_paths=tuple(_string_list(value, "created_paths")),
    )
