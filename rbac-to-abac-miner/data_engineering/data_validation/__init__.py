"""
data_engineering.data_validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Public interface for dataset validation and the independent oracle.

Jayed's loader calls::

    from data_engineering.data_validation import validate_dataset

Tests use::

    from data_engineering.data_validation import brute_force_auth, verify_samples
"""
from data_engineering.data_validation.validator import validate_dataset
from data_engineering.data_validation.oracle import brute_force_auth, verify_samples

__all__ = ["validate_dataset", "brute_force_auth", "verify_samples"]
