"""Central logging for the EduEvidence engine and retrieval layers (plan E4).

The engine is a library: it must never configure handlers or emit to stdout by
itself. Every module obtains its logger here; applications (CLI, dashboard,
tests) opt into output with one call to `enable_console_logging()`.

Usage:
    from engine.log import get_log
    log = get_log("fetch")
    log.info("fallback provider=%s reason=%s", provider, reason)

Stdlib only.
"""

from __future__ import annotations

import logging

_ROOT = "eduevidence"


def get_log(component: str) -> logging.Logger:
    """Return a namespaced logger with a NullHandler default."""
    logger = logging.getLogger(f"{_ROOT}.{component}")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    logger.propagate = True
    return logger


def enable_console_logging(level: int = logging.INFO) -> None:
    """Opt-in root handler for CLI entrypoints (idempotent)."""
    root = logging.getLogger(_ROOT)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"))
        root.addHandler(handler)
    root.setLevel(level)
