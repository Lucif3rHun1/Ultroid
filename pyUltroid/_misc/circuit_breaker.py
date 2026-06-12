"""Circuit breaker for flaky external dependencies.

States:
    CLOSED      requests flow through; failures are counted.
    OPEN        requests short-circuit with ``CircuitOpenError`` until the
                reset timeout elapses.
    HALF_OPEN   one probe request is allowed; success closes the breaker,
                failure re-opens it.
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, TypeVar, Union

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when a call is rejected because the breaker is OPEN."""


class CircuitBreaker:
    """Thread-safe circuit breaker.

    Args:
        name:                 Identifier used in log lines and ``repr``.
        failure_threshold:    Consecutive failures that trip OPEN.
        reset_timeout:        Seconds the breaker stays OPEN before allowing
                              a single HALF_OPEN probe.
        expected_exceptions:  Tuple of exception classes that count as a
                              failure. Anything else propagates untouched.
        logger:               Optional logger; defaults to module logger.
    """

    __slots__ = (
        "name",
        "_failure_threshold",
        "_reset_timeout",
        "_expected",
        "_state",
        "_failures",
        "_opened_at",
        "_lock",
        "_logger",
    )

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        expected_exceptions: tuple = (Exception,),
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if reset_timeout <= 0:
            raise ValueError("reset_timeout must be > 0")
        self.name = name
        self._failure_threshold = failure_threshold
        self._reset_timeout = float(reset_timeout)
        self._expected = expected_exceptions
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: float = 0.0
        self._lock = threading.RLock()
        self._logger = logger or logging.getLogger("pyUltroid.circuit")

    def __repr__(self) -> str:
        return f"<CircuitBreaker {self.name} state={self._state.value}>"

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_half_open_locked()
            return self._state

    def _maybe_half_open_locked(self) -> None:
        if (
            self._state is CircuitState.OPEN
            and time.monotonic() - self._opened_at >= self._reset_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            self._logger.info(
                "Circuit %s: OPEN -> HALF_OPEN after %.1fs", self.name, self._reset_timeout
            )

    def _allow_request(self) -> None:
        with self._lock:
            self._maybe_half_open_locked()
            if self._state is CircuitState.OPEN:
                raise CircuitOpenError(
                    f"Circuit '{self.name}' is OPEN; refusing call"
                )

    def _record_success(self) -> None:
        with self._lock:
            if self._state is not CircuitState.CLOSED:
                self._logger.info(
                    "Circuit %s: %s -> CLOSED after successful call",
                    self.name,
                    self._state.value,
                )
            self._state = CircuitState.CLOSED
            self._failures = 0

    def _record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state is CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                self._logger.warning(
                    "Circuit %s: HALF_OPEN -> OPEN (probe failed)", self.name
                )
            elif (
                self._state is CircuitState.CLOSED
                and self._failures >= self._failure_threshold
            ):
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                self._logger.warning(
                    "Circuit %s: CLOSED -> OPEN after %d failures",
                    self.name,
                    self._failures,
                )

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        self._allow_request()
        try:
            result = func(*args, **kwargs)
        except self._expected:
            self._record_failure()
            raise
        self._record_success()
        return result

    async def acall(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        self._allow_request()
        try:
            result = await func(*args, **kwargs)
        except self._expected:
            self._record_failure()
            raise
        self._record_success()
        return result

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._opened_at = 0.0
