"""Host-side tests of the portable layer, under CPython: src/ is put on the path so `base` imports as on a device."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
