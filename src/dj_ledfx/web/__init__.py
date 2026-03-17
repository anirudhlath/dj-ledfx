"""Web UI package. Requires optional [web] dependencies."""
try:
    import fastapi  # noqa: F401
except ImportError as e:
    raise ImportError(
        "Web UI dependencies not installed. "
        "Install with: uv pip install dj-ledfx[web]"
    ) from e
