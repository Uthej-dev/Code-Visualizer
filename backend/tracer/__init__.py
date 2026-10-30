"""Python execution tracer used by the visualizer.

This package is imported both by the web server (for validation only) and by the
isolated child process that actually executes user code (see ``runner.py``).
It depends on the standard library only.
"""

from .engine import TraceLimits, Tracer, trace_code  # noqa: F401
from .validator import ValidationError, validate_source  # noqa: F401
