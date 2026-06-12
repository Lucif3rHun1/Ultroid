"""Tests for pyUltroid._misc.context.ApplicationContext."""
import pytest

from pyUltroid._misc.context import ApplicationContext, app, bind_from_globals


def test_default_fields_are_none():
    fresh = ApplicationContext()
    assert fresh.bot is None
    assert fresh.asst is None
    assert fresh.vc is None
    assert fresh.db is None
    assert fresh.logs is None
    assert fresh.is_ready() is False


def test_is_ready_true_when_all_present():
    ctx = ApplicationContext(bot="b", asst="a", db="d")
    assert ctx.is_ready() is True


def test_is_ready_false_when_one_missing():
    ctx = ApplicationContext(bot="b", asst="a", db=None)
    assert ctx.is_ready() is False


def test_as_dict():
    ctx = ApplicationContext(bot="b", hndlr="!")
    d = ctx.as_dict()
    assert d["bot"] == "b"
    assert d["hndlr"] == "!"
    assert "db" in d


def test_global_app_singleton_exists():
    assert isinstance(app, ApplicationContext)


def test_bind_from_globals_reads_module():
    import pyUltroid

    # Simulate module-level globals
    pyUltroid.ultroid_bot = "fake_bot"
    pyUltroid.asst = "fake_asst"
    pyUltroid.vcClient = None
    pyUltroid.udB = "fake_db"
    pyUltroid.LOGS = "fake_logs"
    pyUltroid.HNDLR = "!"

    bind_from_globals()

    assert app.bot == "fake_bot"
    assert app.asst == "fake_asst"
    assert app.vc is None
    assert app.db == "fake_db"
    assert app.logs == "fake_logs"
    assert app.hndlr == "!"

    # cleanup
    for k in ("ultroid_bot", "asst", "vcClient", "udB", "LOGS", "HNDLR"):
        if hasattr(pyUltroid, k):
            delattr(pyUltroid, k)


def test_bind_from_globals_handles_missing_attrs():
    """If module hasn't set globals yet, bind_from_globals shouldn't crash."""
    # Re-bind with no module-level globals set
    import pyUltroid

    # Save and clear
    saved = {}
    for k in ("ultroid_bot", "asst", "vcClient", "udB", "LOGS", "HNDLR",
             "DUAL_HNDLR", "SUDO_HNDLR"):
        if hasattr(pyUltroid, k):
            saved[k] = getattr(pyUltroid, k)
            delattr(pyUltroid, k)

    bind_from_globals()  # should not raise

    assert app.bot is None
    assert app.hndlr == "."  # default

    # restore
    for k, v in saved.items():
        setattr(pyUltroid, k, v)
