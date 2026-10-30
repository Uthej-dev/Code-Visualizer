"""FastAPI application: validates requests and delegates execution to the sandbox."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import sandbox
from .config import settings
from .models import Sample, TraceRequest, TraceResponse
from .samples import load_samples

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Code Visualizer API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_run_slots = threading.BoundedSemaphore(settings.max_concurrent_runs)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/samples", response_model=list[Sample])
def samples() -> list[dict]:
    return load_samples()


@app.post("/api/trace", response_model=TraceResponse)
def trace(request: TraceRequest) -> dict:
    # Sync endpoint: FastAPI runs it in a worker thread, so blocking on the
    # child process does not stall the event loop.
    if not _run_slots.acquire(timeout=10):
        raise HTTPException(status_code=429, detail="The server is busy running other programs. Please try again.")
    try:
        result = sandbox.run_code(request.code)
    finally:
        _run_slots.release()
    try:
        return TraceResponse.model_validate(result)
    except Exception:
        logging.getLogger("codeviz").exception("runner produced an invalid trace")
        raise HTTPException(status_code=500, detail="The execution engine produced an invalid result.") from None


# In production, serve the built frontend (frontend/dist) from the same origin.
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
