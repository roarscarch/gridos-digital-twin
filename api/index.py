# Vercel entrypoint — re-exports the FastAPI app
from backend.app.main import app

# Vercel python runtime looks for `app`
__all__ = ["app"]
