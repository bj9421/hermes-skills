"""Visual summary generator — wrapper around the existing visual_gen.py module."""

import os
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from visual_gen import generate_visual
