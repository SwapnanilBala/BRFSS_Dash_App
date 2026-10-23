"""Vercel serverless entry point.

Vercel's Python runtime looks for a module-level WSGI application called ``app``.
Dash wraps Flask, so ``app.server`` from the dashboard is exactly that.

Import cost on a cold start is the 0.68 MB data/panels.json and nothing else —
no pandas, no survey file — so the function is warm in well under a second.
"""

import sys
from pathlib import Path

# api/ sits one level below the project root, where app.py and data/ live.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import server as app  # noqa: E402  (path setup must come first)

__all__ = ["app"]
