"""Shared pytest fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the wallgardend package importable when pytest is run from `daemon/`.
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
