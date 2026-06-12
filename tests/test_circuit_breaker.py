"""Tests for pyUltroid._misc.circuit_breaker.CircuitBreaker."""
import asyncio
import time

import pytest

from pyUltroid._misc.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


def test_starts_closed():
    cb = CircuitBreaker("test", failure_threshold=3, reset_timeout=1.0)
    assert cb.state == CircuitState.CLOSED


def test_opens_after_threshold():
    cb = CircuitBreaker("test", failure_threshold=2, reset_timeout=1.0)

    def boom():
        raise ValueError("nope")

    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(boom)
    assert cb.state == CircuitState.OPEN


def test_open_rejects_calls():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=10.0)

    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        cb.call(boom)
    with pytest.raises(CircuitOpenError):
        cb.call(boom)


def test_open_to_half_open_after_timeout():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05)

    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        cb.call(boom)
    assert cb.state == CircuitState.OPEN
    time.sleep(0.1)
    assert cb.state == CircuitState.HALF_OPEN


def test_half_open_success_closes():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05)

    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        cb.call(boom)
    time.sleep(0.1)
    result = cb.call(lambda: "ok")
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED


def test_half_open_failure_reopens():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05)

    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        cb.call(boom)
    time.sleep(0.1)
    assert cb.state == CircuitState.HALF_OPEN
    with pytest.raises(ValueError):
        cb.call(boom)
    assert cb.state == CircuitState.OPEN


def test_expected_exceptions_filter():
    """An exception type not in expected_exceptions should not count."""
    cb = CircuitBreaker(
        "test", failure_threshold=1, reset_timeout=10.0,
        expected_exceptions=(ValueError,),
    )

    def raises_key():
        raise KeyError("not counted")

    # KeyError shouldn't trip the breaker
    for _ in range(5):
        with pytest.raises(KeyError):
            cb.call(raises_key)
    assert cb.state == CircuitState.CLOSED


def test_successful_call_resets_failures():
    cb = CircuitBreaker("test", failure_threshold=3, reset_timeout=10.0)

    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        cb.call(boom)
    with pytest.raises(ValueError):
        cb.call(boom)
    # Two failures, one more would trip the breaker
    assert cb.call(lambda: 1) == 1
    with pytest.raises(ValueError):
        cb.call(boom)
    with pytest.raises(ValueError):
        cb.call(boom)
    # After success, counter reset — still CLOSED
    assert cb.state == CircuitState.CLOSED


def test_reset():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=10.0)

    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        cb.call(boom)
    assert cb.state == CircuitState.OPEN
    cb.reset()
    assert cb.state == CircuitState.CLOSED


def test_repr():
    cb = CircuitBreaker("repro", failure_threshold=1, reset_timeout=1.0)
    assert "repro" in repr(cb)
    assert "CircuitBreaker" in repr(cb)


def test_invalid_failure_threshold():
    with pytest.raises(ValueError):
        CircuitBreaker("test", failure_threshold=0, reset_timeout=1.0)


def test_invalid_reset_timeout():
    with pytest.raises(ValueError):
        CircuitBreaker("test", failure_threshold=1, reset_timeout=0)


def test_async_acall_success():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05)

    async def coro():
        return "good"

    result = asyncio.run(cb.acall(coro))
    assert result == "good"
    assert cb.state == CircuitState.CLOSED


def test_async_acall_failure_trips():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05)

    async def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        asyncio.run(cb.acall(boom))
    assert cb.state == CircuitState.OPEN


def test_async_acall_open_rejects():
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=10.0)

    async def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        asyncio.run(cb.acall(boom))
    with pytest.raises(CircuitOpenError):
        asyncio.run(cb.acall(boom))
