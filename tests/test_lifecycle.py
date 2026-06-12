"""Tests for pyUltroid._misc.lifecycle."""
import pytest

from pyUltroid._misc import lifecycle as L


@pytest.fixture(autouse=True)
def _clear_hooks():
    """Reset the global hook list and flags between tests."""
    L._SHUTDOWN_HOOKS.clear()
    L._shutdown_in_progress = False
    yield
    L._SHUTDOWN_HOOKS.clear()
    L._shutdown_in_progress = False


def test_register_and_run_hooks():
    calls = []
    L.register_shutdown_hook(lambda: calls.append("a"))
    L.register_shutdown_hook(lambda: calls.append("b"))
    L._run_hooks()
    assert calls == ["a", "b"]


def test_unregister_hook():
    calls = []
    h1 = lambda: calls.append("a")  # noqa: E731
    h2 = lambda: calls.append("b")  # noqa: E731
    L.register_shutdown_hook(h1)
    L.register_shutdown_hook(h2)
    L.unregister_shutdown_hook(h1)
    L._run_hooks()
    assert calls == ["b"]


def test_unregister_unknown_hook_is_safe():
    L.unregister_shutdown_hook(lambda: None)  # no exception


def test_hooks_idempotent():
    calls = []
    L.register_shutdown_hook(lambda: calls.append("a"))
    L._run_hooks()
    L._run_hooks()
    assert calls == ["a"]  # only once


def test_broken_hook_does_not_block_others():
    calls = []
    L.register_shutdown_hook(lambda: calls.append("a"))
    L.register_shutdown_hook(lambda: 1 / 0)  # raises
    L.register_shutdown_hook(lambda: calls.append("b"))
    L._run_hooks()  # must not raise
    assert calls == ["a", "b"]


def test_register_requires_callable():
    with pytest.raises(TypeError):
        L.register_shutdown_hook("not callable")


def test_install_signal_handlers_smoke():
    """Smoke test: install_signal_handlers does not crash on no-op loop."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        L.install_signal_handlers(loop)
    finally:
        loop.close()
