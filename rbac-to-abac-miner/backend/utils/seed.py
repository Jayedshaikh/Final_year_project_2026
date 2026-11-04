"""Utility for managing reproducible random seeds.

Every stochastic step must accept a random_seed parameter.
Default seed is 42. Never rely on global random state.
"""
import random

import numpy as np


def set_global_seed(seed: int = 42) -> None:
    """Set random seeds for Python, NumPy, and any other relevant libraries.

    Args:
        seed: Integer seed value. Default 42.
    """
    random.seed(seed)
    np.random.seed(seed)


def get_rng(seed: int = 42) -> np.random.Generator:
    """Return a NumPy default_rng instance with the given seed.

    Args:
        seed: Integer seed value. Default 42.

    Returns:
        A seeded numpy.random.Generator instance.
    """
    return np.random.default_rng(seed)
