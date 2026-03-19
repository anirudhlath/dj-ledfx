"""Skip all web tests when the optional 'web' extra is not installed."""

import pytest

fastapi = pytest.importorskip("fastapi", reason="web extra not installed (uv sync --extra web)")
