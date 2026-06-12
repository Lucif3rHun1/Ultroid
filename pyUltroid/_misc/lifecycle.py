"""Process lifecycle: signal handlers and graceful shutdown.

Use ``install_signal_handlers(loop)`` once after the asyncio loop exists
but before ``run_until_disconnected``. ``register_shutdown_hook(callable)``
to register additional cleanup work that should run on graceful exit.

On Unix this installs SIGINT and SIGTERM handlers via the running loop
(so they cooperate with ``run_until_disconnected``). On Windows, only
SIGINT/SIGBREAK are wired; SIGTERM is unsupported and falls back to the
default handler.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading
from typing import Callable, List

_LOGGER = logging.getLogger("pyUltroid.lifecycle")
_SHUTDOWN_HOOKS: List[Callable[[], None]] = []
_SHUTDOWN_LOCK = threading.Lock()
_shutdown_in_progress = False
_graceful = True


def register_shutdown_hook(func: Callable[[], None]) -> None:
    """Register a sync cleanup callable to run on graceful shutdown.

    Exceptions raised by hooks are logged and swallowed so a single
    broken hook does not prevent subsequent ones from running.
    """
    if not callable(func):
        raise TypeError("shutdown hook must be callable")
    with _SHUTDOWN_LOCK:
        _SHUTDOWN_HOOKS.append(func)


def unregister_shutdown_hook(func: Callable[[], None]) -> None:
    with _SHUTDOWN_LOCK:
        try:
            _SHUTDOWN_HOOKS.remove(func)
        except ValueError:
            pass


def _run_hooks() -> None:
    global _shutdown_in_progress
    with _SHUTDOWN_LOCK:
        if _shutdown_in_progress:
            return
        _shutdown_in_progress = True
        hooks = list(_SHUTDOWN_HOOKS)
    for hook in hooks:
        try:
            hook()
        except Exception as exc:
            _LOGGER.warning("shutdown hook %r failed: %s", hook, exc)


def request_shutdown(graceful: bool = True) -> None:
    """Trigger graceful shutdown from anywhere in the process."""
    global _graceful
    _graceful = graceful
    _LOGGER.info("Shutdown requested (graceful=%s)", graceful)
    _run_hooks()
    if graceful:
        sys.exit(0)
    else:
        sys.exit(1)


def install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Wire SIGINT/SIGTERM (and SIGBREAK on Windows) to a graceful stop."""

    def _handler(signame: str) -> None:
        _LOGGER.info("Received %s, initiating graceful shutdown", signame)
        try:
            loop.call_soon_threadsafe(_run_hooks)
        except RuntimeError:
            _run_hooks()
        try:
            loop.call_soon_threadsafe(loop.stop)
        except RuntimeError:
            pass

    sig_pairs: list[tuple[int, str]] = []
    if hasattr(signal, "SIGINT"):
        sig_pairs.append((signal.SIGINT, "SIGINT"))
    if hasattr(signal, "SIGTERM"):
        sig_pairs.append((signal.SIGTERM, "SIGTERM"))
    if hasattr(signal, "SIGBREAK") and sys.platform == "win32":
        sig_pairs.append((signal.SIGBREAK, "SIGBREAK"))

    for sig, name in sig_pairs:
        try:
            loop.add_signal_handler(sig, _handler, name)
        except (NotImplementedError, RuntimeError) as exc:
            _LOGGER.debug("Could not install handler for %s: %s", name, exc)
            try:
                signal.signal(sig, lambda *_: _handler(name))
            except Exception as exc2:
                _LOGGER.debug("Fallback signal.signal failed for %s: %s", name, exc2)
