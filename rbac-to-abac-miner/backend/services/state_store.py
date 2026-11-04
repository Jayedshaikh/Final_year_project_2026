"""In-memory state store with JSON file persistence.

Stores datasets, runs, and policies in memory (fast) and flushes to
backend/runs/*.json (git-ignored) for restart recovery.

Decision D-007: in-memory + JSON files.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from backend.utils.storage import (
    load_dataset_meta,
    load_policy,
    load_run,
    save_dataset_meta,
    save_policy,
    save_run,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# In-memory stores: { id -> dict }
_datasets: Dict[str, Dict[str, Any]] = {}
_runs: Dict[str, Dict[str, Any]] = {}
_policies: Dict[str, Dict[str, Any]] = {}

# Counters for generating IDs
_dataset_counter = 0
_run_counter = 0
_policy_counter = 0


# --------------------------------------------------------------------------- #
# ID generation
# --------------------------------------------------------------------------- #

def next_dataset_id() -> str:
    """Generate and return the next dataset ID (e.g. 'ds_001').

    Returns:
        Unique dataset identifier string.
    """
    global _dataset_counter
    with _lock:
        _dataset_counter += 1
        return f"ds_{_dataset_counter:03d}"


def next_run_id() -> str:
    """Generate and return the next run ID (e.g. 'run_001').

    Returns:
        Unique run identifier string.
    """
    global _run_counter
    with _lock:
        _run_counter += 1
        return f"run_{_run_counter:03d}"


def next_policy_id() -> str:
    """Generate and return the next policy ID (e.g. 'pol_001').

    Returns:
        Unique policy identifier string.
    """
    global _policy_counter
    with _lock:
        _policy_counter += 1
        return f"pol_{_policy_counter:03d}"


# --------------------------------------------------------------------------- #
# Dataset operations
# --------------------------------------------------------------------------- #

def store_dataset(dataset_id: str, data: Dict[str, Any]) -> None:
    """Store dataset metadata in memory and on disk.

    Args:
        dataset_id: Dataset identifier.
        data: Metadata dict (must be JSON-serialisable for persistence).
    """
    with _lock:
        _datasets[dataset_id] = data
    try:
        save_dataset_meta(dataset_id, data)
    except Exception as exc:
        logger.warning("Could not persist dataset %s to disk: %s", dataset_id, exc)


def get_dataset(dataset_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve dataset metadata.

    Checks in-memory store first; falls back to disk.

    Args:
        dataset_id: Dataset identifier.

    Returns:
        Metadata dict, or None if not found.
    """
    data = _datasets.get(dataset_id)
    if data is not None:
        return data
    # Fall back to disk
    data = load_dataset_meta(dataset_id)
    if data is not None:
        with _lock:
            _datasets[dataset_id] = data
    return data


# --------------------------------------------------------------------------- #
# Run operations
# --------------------------------------------------------------------------- #

def store_run(run_id: str, data: Dict[str, Any]) -> None:
    """Store run data in memory and on disk.

    Args:
        run_id: Run identifier.
        data: Run data dict.
    """
    with _lock:
        _runs[run_id] = data
    try:
        save_run(run_id, data)
    except Exception as exc:
        logger.warning("Could not persist run %s to disk: %s", run_id, exc)


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve run data.

    Args:
        run_id: Run identifier.

    Returns:
        Run data dict, or None if not found.
    """
    data = _runs.get(run_id)
    if data is not None:
        return data
    data = load_run(run_id)
    if data is not None:
        with _lock:
            _runs[run_id] = data
    return data


# --------------------------------------------------------------------------- #
# Policy operations
# --------------------------------------------------------------------------- #

def store_policy(policy_id: str, data: Dict[str, Any]) -> None:
    """Store policy data in memory and on disk.

    Args:
        policy_id: Policy identifier.
        data: Policy data dict.
    """
    with _lock:
        _policies[policy_id] = data
    try:
        save_policy(policy_id, data)
    except Exception as exc:
        logger.warning("Could not persist policy %s to disk: %s", policy_id, exc)


def get_policy(policy_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve policy data.

    Args:
        policy_id: Policy identifier.

    Returns:
        Policy data dict, or None if not found.
    """
    data = _policies.get(policy_id)
    if data is not None:
        return data
    data = load_policy(policy_id)
    if data is not None:
        with _lock:
            _policies[policy_id] = data
    return data
