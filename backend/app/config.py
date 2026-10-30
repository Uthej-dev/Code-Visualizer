"""Server configuration, overridable through environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    wall_timeout_seconds: float = _float("CV_WALL_TIMEOUT", 5.0)
    cpu_seconds: int = _int("CV_CPU_SECONDS", 4)
    memory_mb: int = _int("CV_MEMORY_MB", 256)
    max_steps: int = _int("CV_MAX_STEPS", 1000)
    max_output_chars: int = _int("CV_MAX_OUTPUT_CHARS", 20_000)
    max_trace_bytes: int = _int("CV_MAX_TRACE_BYTES", 8_000_000)
    max_concurrent_runs: int = _int("CV_MAX_CONCURRENT_RUNS", 4)
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.environ.get("CV_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()
    )


settings = Settings()
