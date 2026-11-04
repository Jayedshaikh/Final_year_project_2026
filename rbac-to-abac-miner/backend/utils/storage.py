"""Persistent storage helpers for run state.

State is stored in-memory (fast) and written to JSON files under backend/runs/
(git-ignored) so that a server restart can reload the last state.

Decision D-007: In-memory + JSON files; SQLite only if needed.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Directory relative to the repository root (resolved at import time)
_RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def _ensure_runs_dir() -> Path:
    """Create the runs directory if it does not exist.

    Returns:
        Path to the runs directory.
    """
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return _RUNS_DIR


def save_run(run_id: str, data: Dict[str, Any]) -> None:
    """Persist a run record to disk as JSON.

    Args:
        run_id: Unique run identifier (e.g. "run_001").
        data: Dictionary of run data; must be JSON-serialisable.

    Raises:
        TypeError: If data contains non-serialisable types.
    """
    runs_dir = _ensure_runs_dir()
    path = runs_dir / f"{run_id}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    logger.debug("Saved run %s to %s", run_id, path)


def load_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Load a run record from disk.

    Args:
        run_id: Unique run identifier.

    Returns:
        The run dict, or None if the file does not exist.
    """
    path = _RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_dataset_meta(dataset_id: str, data: Dict[str, Any]) -> None:
    """Persist dataset metadata to disk as JSON.

    Args:
        dataset_id: Unique dataset identifier (e.g. "ds_001").
        data: Metadata dict; must be JSON-serialisable.
    """
    runs_dir = _ensure_runs_dir()
    path = runs_dir / f"{dataset_id}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    logger.debug("Saved dataset metadata %s to %s", dataset_id, path)


def load_dataset_meta(dataset_id: str) -> Optional[Dict[str, Any]]:
    """Load dataset metadata from disk.

    Args:
        dataset_id: Unique dataset identifier.

    Returns:
        The metadata dict, or None if not found.
    """
    path = _RUNS_DIR / f"{dataset_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_policy(policy_id: str, data: Dict[str, Any]) -> None:
    """Persist a policy record to disk as JSON.

    Args:
        policy_id: Unique policy identifier (e.g. "pol_001").
        data: Policy dict; must be JSON-serialisable.
    """
    runs_dir = _ensure_runs_dir()
    path = runs_dir / f"{policy_id}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    logger.debug("Saved policy %s to %s", policy_id, path)


def load_policy(policy_id: str) -> Optional[Dict[str, Any]]:
    """Load a policy record from disk.

    Args:
        policy_id: Unique policy identifier.

    Returns:
        The policy dict, or None if not found.
    """
    path = _RUNS_DIR / f"{policy_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
