"""Configuration loader for the backend.

Loads config/mining_config.json relative to the repository root and caches it.
Request-level overrides (from TrainingConfigRequest) take precedence over these defaults.

Never store secrets here. The config file has no credentials.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Path resolved relative to this file: backend/utils/ -> backend/ -> repo root -> config/
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "mining_config.json"

_cache: Optional[Dict[str, Any]] = None


def load_config(force_reload: bool = False) -> Dict[str, Any]:
    """Load and cache the mining configuration from config/mining_config.json.

    Args:
        force_reload: If True, bypass the cache and reload from disk.

    Returns:
        Configuration dict. Returns empty dict and logs a warning if the file
        cannot be read (allows the application to start with defaults).
    """
    global _cache
    if _cache is not None and not force_reload:
        return _cache

    if not _CONFIG_PATH.exists():
        logger.warning(
            "Config file not found at %s; all values will use request defaults.", _CONFIG_PATH
        )
        _cache = {}
        return _cache

    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
            _cache = json.load(fh)
        logger.debug("Loaded config from %s (version %s)", _CONFIG_PATH, _cache.get("config_version"))
        return _cache
    except Exception as exc:
        logger.warning("Failed to load config from %s: %s; using empty config.", _CONFIG_PATH, exc)
        _cache = {}
        return _cache


def get(key: str, default: Any = None) -> Any:
    """Get a top-level config value by key.

    Args:
        key: Top-level key in mining_config.json.
        default: Returned if the key is absent.

    Returns:
        The value, or default.
    """
    return load_config().get(key, default)


def get_wsc_weights() -> Dict[str, float]:
    """Return WSC weight configuration.

    Returns:
        Dict with w_rule, w_cond, w_val (defaults: 1.0, 1.0, 0.5).
    """
    cfg = load_config()
    defaults = {"w_rule": 1.0, "w_cond": 1.0, "w_val": 0.5}
    return {**defaults, **cfg.get("wsc_weights", {})}


def get_preprocessing_config() -> Dict[str, Any]:
    """Return preprocessing configuration section.

    Returns:
        Dict with missing_value_strategy etc.
    """
    return load_config().get("preprocessing", {})
