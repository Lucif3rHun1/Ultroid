"""Tests for Phase 3 utilities: JSON logging, health, config validation."""
import asyncio
import io
import json
import logging
import os

import pytest

from pyUltroid._misc.config_validation import (
    ValidationError,
    report as report_validation,
    validate_env,
)
from pyUltroid._misc.health import _DB_BREAKER, health_check_loop
from pyUltroid._misc.json_log import JsonFormatter, is_json_enabled


# --- JsonFormatter --------------------------------------------------------

def test_json_basic_line():
    fmt = JsonFormatter(hostname="test-host", static={"app": "ultroid"})
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(fmt)
    log = logging.getLogger("test.json.basic")
    log.handlers = [h]
    log.setLevel(logging.INFO)
    log.propagate = False

    log.info("hello world")
    line = buf.getvalue().strip()
    obj = json.loads(line)
    for k in ("ts", "level", "logger", "msg", "pid", "thread", "host"):
        assert k in obj
    assert obj["host"] == "test-host"
    assert obj["app"] == "ultroid"
    assert obj["msg"] == "hello world"


def test_json_extras():
    fmt = JsonFormatter()
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(fmt)
    log = logging.getLogger("test.json.extras")
    log.handlers = [h]
    log.setLevel(logging.INFO)
    log.propagate = False

    log.info("test", extra={"user_id": 42, "chat": -100})
    obj = json.loads(buf.getvalue().strip())
    assert obj["user_id"] == 42
    assert obj["chat"] == -100


def test_json_exception():
    fmt = JsonFormatter()
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(fmt)
    log = logging.getLogger("test.json.exc")
    log.handlers = [h]
    log.setLevel(logging.ERROR)
    log.propagate = False
    try:
        raise ValueError("boom")
    except Exception:
        log.exception("failure")
    obj = json.loads(buf.getvalue().strip())
    assert "exc" in obj
    assert "ValueError: boom" in obj["exc"]


def test_json_falls_back_to_repr():
    fmt = JsonFormatter()
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(fmt)
    log = logging.getLogger("test.json.repr")
    log.handlers = [h]
    log.setLevel(logging.INFO)
    log.propagate = False

    class Foo: pass

    log.info("weird", extra={"obj": Foo()})
    obj = json.loads(buf.getvalue().strip())
    assert obj["obj"].startswith("<")


# --- is_json_enabled ------------------------------------------------------

def test_is_json_enabled_off_by_default(monkeypatch):
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    assert is_json_enabled() is False


def test_is_json_enabled_env(monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "json")
    assert is_json_enabled() is True
    monkeypatch.setenv("LOG_FORMAT", "JSON")
    assert is_json_enabled() is True
    monkeypatch.setenv("LOG_FORMAT", "plain")
    assert is_json_enabled() is False


# --- validate_env ---------------------------------------------------------

def test_validate_env_empty():
    errs = validate_env({})
    assert any("SESSION" in e.key for e in errs)
    assert any("database" in e.reason for e in errs)


def test_validate_env_valid():
    errs = validate_env({
        "API_ID": "12345",
        "API_HASH": "abcdef0123456789abcdef0123456789",
        "SESSION": "BQA" + "X" * 200,
        "REDIS_URI": "redis://localhost:6379/0",
    })
    assert errs == []


def test_validate_env_session_with_padding():
    """Base64-padded session (ending with '=' or '==') must be accepted."""
    errs = validate_env({
        "API_ID": "12345",
        "API_HASH": "abcdef0123456789abcdef0123456789",
        "SESSION": "BQA" + "X" * 200 + "=",
        "REDIS_URI": "redis://localhost:6379/0",
    })
    assert not any(e.key == "SESSION" for e in errs), \
        f"unexpected: {[e for e in errs if e.key == 'SESSION']}"


def test_validate_env_session_too_short():
    """Tiny session is rejected."""
    errs = validate_env({"SESSION": "abc"})
    assert any(e.key == "SESSION" for e in errs)


def test_validate_env_bad_api_id():
    for bad in ("abc", "12.5", "-1", ""):
        errs = validate_env({"API_ID": bad})
        assert any(e.key == "API_ID" for e in errs)


def test_validate_env_bad_api_hash():
    for bad in ("", "short", "your_api_hash_here", "PLACEHOLDER_value"):
        errs = validate_env({"API_HASH": bad})
        assert any(e.key == "API_HASH" for e in errs)


def test_validate_env_bad_db_uri():
    errs = validate_env({"REDIS_URI": "http://example.com"})
    assert any(e.key == "REDIS_URI" for e in errs)


def test_validate_env_multiple_dbs():
    errs = validate_env({
        "REDIS_URI": "redis://x",
        "MONGO_URI": "mongodb://x",
    })
    assert any("more than one" in e.reason for e in errs)


def test_validate_env_heroku_partial():
    errs1 = validate_env({"HEROKU_APP_NAME": "app"})
    errs2 = validate_env({"HEROKU_API": "key"})
    assert errs1 and errs2
    errs3 = validate_env({"HEROKU_APP_NAME": "app", "HEROKU_API": "key"})
    assert not any("HEROKU" in e.key for e in errs3)


def test_report_validation_returns_count():
    log = logging.getLogger("test.report")
    n = report_validation([], log)
    assert n == 0
    errs = [ValidationError("X", "y", "z")]
    n = report_validation(errs, log)
    assert n == 1


# --- health_check_loop ----------------------------------------------------

class _GoodDB:
    def __init__(self):
        self.calls = 0
        self.name = "GoodDB"

    def ping(self):
        self.calls += 1
        return 1


class _BadDB:
    def __init__(self):
        self.calls = 0
        self.name = "BadDB"

    def ping(self):
        self.calls += 1
        raise ConnectionError("dead")


@pytest.fixture
def reset_breaker():
    _DB_BREAKER.reset()
    yield
    _DB_BREAKER.reset()


async def _run_loop_safely(coro, cancel_after=0.4):
    task = asyncio.create_task(coro)
    await asyncio.sleep(cancel_after)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return task


@pytest.mark.asyncio
async def test_health_loop_healthy(reset_breaker):
    db = _GoodDB()
    await _run_loop_safely(
        health_check_loop(db, interval=0.05, name="good"),
        cancel_after=0.3,
    )
    assert db.calls >= 3


@pytest.mark.asyncio
async def test_health_loop_failing_opens_breaker(reset_breaker):
    db = _BadDB()
    await _run_loop_safely(
        health_check_loop(db, interval=0.05, name="bad"),
        cancel_after=0.5,
    )
    from pyUltroid._misc.circuit_breaker import CircuitState
    assert _DB_BREAKER.state == CircuitState.OPEN
    # The DB is called at least 3 times before the circuit opens
    assert db.calls >= 3


@pytest.mark.asyncio
async def test_health_loop_recovers(reset_breaker):
    class _Flakey:
        def __init__(self):
            self.fail = True
            self.calls = 0
        def ping(self):
            self.calls += 1
            if self.fail:
                raise ConnectionError("flakey")
            return 1

    db = _Flakey()
    task = asyncio.create_task(health_check_loop(db, interval=0.05, name="flakey"))
    await asyncio.sleep(0.2)
    db.fail = False
    _DB_BREAKER.reset()  # force the circuit closed so the next ping goes through
    await asyncio.sleep(0.4)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert db.calls >= 3


@pytest.mark.asyncio
async def test_health_loop_rejects_bad_interval():
    with pytest.raises(ValueError):
        await health_check_loop(_GoodDB(), interval=0)
