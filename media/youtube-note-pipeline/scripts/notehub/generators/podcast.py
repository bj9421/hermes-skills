"""Podcast generator — wrapper around the existing podcast.py module."""

import os
import sys

# Add parent scripts dir to path for imports
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# Import from existing podcast.py (reuse, don't rewrite)
from podcast import produce_podcast as _produce_podcast
