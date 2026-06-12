"""Shared pytest fixtures for the Ultroid test suite."""
import sys
from pathlib import Path

# Make the pyUltroid package importable without installing.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
