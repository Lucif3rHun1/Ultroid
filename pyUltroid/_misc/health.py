"""Background connection health monitor.

Pings the active database (and optionally the Telegram clients) on a
fixed cadence. Surfaces failures via the standard logger so an
operator can correlate the timestamps with deploys or platform
incidents. Inspired by the existing ``keep_redis_alive`` helper, but
generalised across Redis / Mongo / SQL.

Key differences from the keepalive updater:

- Works for every DB type, not just Redis.
- Counts consecutive failures and escalates the log severity after
  three in a row, so a single transient blip does not page anyone
  but a sustained outage lights up the logs.
- Cancels cleanly when the loop task is cancelled.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .._misc.circuit_breaker import CircuitBreaker, CircuitOpenError

_LOGGER = logging.getLogger("pyUltroid.health")
_DEFAULT_INTERVAL = 60.0
_ESCALATE_AFTER = 3

_DB_BREAKER = CircuitBreaker(
    "db_health",
    failure_threshold=3,
    reset_timeout=120.0,
    expected_exceptions=(Exception,),
)


def _ping(db: Any) -> None:
    """Synchronous ping for any DB. Raises on failure."""
    if db is None:
        raise RuntimeError("db is not configured")
    ping = getattr(db, "ping", None)
    if not callable(ping):
        raise RuntimeError(f"db {type(db).__name__} has no ping() method")
    result = ping()
    if result is False or result == 0:
        raise RuntimeError(f"ping returned {result!r}")


async def health_check_loop(
    db: Any,
    interval: float = _DEFAULT_INTERVAL,
    name: str = "database",
) -> None:
    """Run a periodic ping on *db* until cancelled.

    Args:
        db:        Anything with a ``ping()`` method that raises on
                   failure (or returns ``False``/``0``).
        interval:  Seconds between checks.
        name:      Human label used in log lines.
    """
    if interval < 0.01:
        raise ValueError("interval must be >= 0.01s")
    failures = 0

    while True:
        try:
            _DB_BREAKER.call(_ping, db)
            if failures:
                _LOGGER.info(
                    "Health check recovered for %s after %d failure(s)", name, failures
                )
            failures = 0
        except CircuitOpenError:
            _LOGGER.warning(
                "Health check skipping %s: circuit OPEN (next probe in %.0fs)",
                name,
                interval,
            )
            failures += 1
        except Exception as exc:
            failures += 1
            if failures >= _ESCALATE_AFTER:
                _LOGGER.error(
                    "Health check FAILED for %s (%d consecutive): %s",
                    name,
                    failures,
                    exc,
                    exc_info=False,
                )
            else:
                _LOGGER.warning("Health check failed for %s: %s", name, exc)

        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            _LOGGER.info("Health check loop cancelled (%s)", name)
            raise


def schedule_health_check(
    loop: asyncio.AbstractEventLoop,
    db: Any,
    interval: float = _DEFAULT_INTERVAL,
    name: str = "database",
) -> "asyncio.Task[None]":
    """Schedule the health check on *loop* and return the Task."""
    return loop.create_task(health_check_loop(db, interval=interval, name=name))


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
