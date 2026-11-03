import importlib.util

import pytest

HAS_LAB = importlib.util.find_spec("microduck_local") is not None
needs_lab = pytest.mark.skipif(not HAS_LAB, reason="Microduck Lab (microduck_local) is not installed")
