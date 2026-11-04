"""Root conftest.py — ensures the repository root is on sys.path for all tests.

This lets pytest discover modules as `from backend.xxx import ...` and
`from shared.schemas import ...` regardless of the working directory.
"""
import sys
from pathlib import Path

# Repository root (the directory containing this file)
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
