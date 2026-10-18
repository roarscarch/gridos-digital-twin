# Vercel serverless entrypoint.
# Vercel's Python runtime imports this module and serves the ASGI `app`
# (FastAPI is ASGI-native — no Mangum adapter needed on current runtimes).
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.main import app  # noqa: E402  (must come after sys.path fix)

__all__ = ["app"]

