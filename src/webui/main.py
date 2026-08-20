from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.webui import routes_cameras, routes_capture, routes_config, routes_live

app = FastAPI(title="video-capture-bundler config UI")

# Register API routes before mounting the SPA static files, so /api/* always wins.
app.include_router(routes_config.router)
app.include_router(routes_cameras.router)
app.include_router(routes_capture.router)
app.include_router(routes_live.router)

_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
