"""Loads the sample programs shared with the frontend (``shared/samples``)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "shared" / "samples"


@lru_cache(maxsize=1)
def load_samples() -> list[dict]:
    manifest = json.loads((SAMPLES_DIR / "manifest.json").read_text())
    samples = []
    for entry in manifest:
        code = (SAMPLES_DIR / entry["file"]).read_text()
        samples.append({
            "id": entry["id"],
            "title": entry["title"],
            "description": entry["description"],
            "concepts": entry["concepts"],
            "code": code,
        })
    return samples
