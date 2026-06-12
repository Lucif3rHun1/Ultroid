"""Application-wide singleton state container.

This is an additive, backward-compatible wrapper around the existing
module-level globals in ``pyUltroid/__init__.py``. Existing code can
continue to import ``from pyUltroid import udB, ultroid_bot``; new code
can prefer ``from pyUltroid._misc.context import app`` and access
``app.bot``, ``app.db``, etc.

The ``ApplicationContext`` is a single dataclass instance set up at
import time. It is intentionally a thin holder — it does not own any
lifecycle, just provides a typed handle to the same objects already
in use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from telethonpatch import TelegramClient
    from ..startup._database import _BaseDatabase
    from logging import Logger


@dataclass
class ApplicationContext:
    """Holds the long-lived singletons that the rest of the code uses.

    All fields default to ``None`` so the type can be imported even
    before ``pyUltroid`` is fully initialised (e.g., by type checkers
    or test harnesses).
    """

    bot: Optional["TelegramClient"] = None
    asst: Optional["TelegramClient"] = None
    vc: Optional["TelegramClient"] = None
    db: Optional["_BaseDatabase"] = None
    logs: Optional["Logger"] = None
    hndlr: str = "."
    dual_hndlr: str = "/"
    sudo_hndlr: str = "."

    def is_ready(self) -> bool:
        return self.bot is not None and self.asst is not None and self.db is not None

    def as_dict(self) -> "dict[str, Any]":
        return {
            "bot": self.bot,
            "asst": self.asst,
            "vc": self.vc,
            "db": self.db,
            "logs": self.logs,
            "hndlr": self.hndlr,
            "dual_hndlr": self.dual_hndlr,
            "sudo_hndlr": self.sudo_hndlr,
        }


app = ApplicationContext()
"""The process-wide application context. Populated during ``pyUltroid``
import. Use this in new code in preference to module-level globals.
"""


def bind_from_globals() -> None:
    """Copy the module-level globals into the context.

    Called from ``pyUltroid.__init__`` after all singletons have been
    assigned. Safe to call multiple times; later calls refresh the
    fields.
    """
    import pyUltroid as _pu

    app.bot = getattr(_pu, "ultroid_bot", None)
    app.asst = getattr(_pu, "asst", None)
    app.vc = getattr(_pu, "vcClient", None)
    app.db = getattr(_pu, "udB", None)
    app.logs = getattr(_pu, "LOGS", None)
    app.hndlr = getattr(_pu, "HNDLR", ".") or "."
    app.dual_hndlr = getattr(_pu, "DUAL_HNDLR", "/") or "/"
    app.sudo_hndlr = getattr(_pu, "SUDO_HNDLR", app.hndlr) or app.hndlr
