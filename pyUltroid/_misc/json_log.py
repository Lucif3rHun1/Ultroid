"""Structured (JSON) log formatter and install helper.

Use when ``LOG_FORMAT=json`` is set in the environment (or
``udB.get_key("LOG_FORMAT") == "json"``). Each record is emitted as a
single line of JSON with stable keys for log-aggregator ingestion.

Plain-text logging is unchanged when the env var is unset; this module
is purely additive.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import time
from typing import Any, Dict, Optional

# Stable keys so dashboards can rely on the field names.
_RESERVED_LOGRECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Emit each LogRecord as a single line of JSON.

    The record's *extras* (anything passed via ``logger.info("x", extra={...})``)
    are merged into the top-level object under their own keys.
    """

    def __init__(self, *, hostname: Optional[str] = None, static: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self._hostname = hostname or socket.gethostname()
        self._static = dict(static or {})

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)
            ) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "pid": record.process,
            "thread": record.threadName,
            "host": self._hostname,
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        for key, value in record.__dict__.items():
            if key in _RESERVED_LOGRECORD_ATTRS or key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)

        payload.update(self._static)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def is_json_enabled() -> bool:
    """True when the env or DB says we should emit JSON."""
    val = os.environ.get("LOG_FORMAT", "").strip().lower()
    if val == "json":
        return True
    if val:
        return False
    try:
        from .. import udB  # type: ignore

        if udB is not None and getattr(udB, "get_key", None):
            stored = udB.get_key("LOG_FORMAT")
            if isinstance(stored, str) and stored.strip().lower() == "json":
                return True
    except Exception:
        pass
    return False


def install_json_handler(logger: logging.Logger, level: int = logging.INFO) -> bool:
    """Attach a JSON StreamHandler to *logger* if not already present.

    Returns ``True`` if a handler was added, ``False`` otherwise.
    """
    for h in logger.handlers:
        if isinstance(h, _JsonStreamHandler):
            return False

    handler = _JsonStreamHandler()
    handler.setLevel(level)
    logger.addHandler(handler)
    logger.setLevel(min(logger.level or logging.NOTSET, level) if logger.level else level)
    return True


class _JsonStreamHandler(logging.StreamHandler):
    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(JsonFormatter())
