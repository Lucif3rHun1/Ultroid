# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
# pyright: reportImportCycles=false, reportConstantRedefinition=false
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/TeamUltroid/pyUltroid/blob/main/LICENSE>.

import os
import sys
from typing import Any, cast
import telethonpatch
from telethon.sessions import StringSession
from .version import __version__

run_as_module = __package__ in sys.argv or sys.argv[0] == "-m"


class ULTConfig:
    lang = "en"
    thumb = "resources/extras/ultroid.jpg"


if run_as_module:
    import time

    from .configs import Var
    from .startup import *
    from .startup._database import UltroidDB
    from .startup.BaseClient import UltroidClient
    from .startup.connections import validate_session, vc_connection
    from .startup.funcs import (
        _version_changes,
        autobot,
        enable_inline,
        set_startup_state,
        update_envs,
    )
    from .version import ultroid_version

    if not os.path.exists("./plugins"):
        LOGS.error(
            "'plugins' folder not found!\nMake sure that, you are on correct path."
        )
        exit()

    start_time = time.time()
    _ult_cache = {}
    from collections import deque

    _IGNORE_EVAL_MAX_SIZE = 4096
    _ignore_eval = deque(maxlen=_IGNORE_EVAL_MAX_SIZE)

    udB = UltroidDB()
    update_envs()

    from ._misc.config_validation import validate_env, report as _report_validation

    _validation_errors = _report_validation(
        validate_env({k: v for k, v in os.environ.items()}),
        LOGS,
    )

    LOGS.info(f"Connecting to {udB.name}...")
    if udB.ping():
        LOGS.info(f"Connected to {udB.name} Successfully!")

    prev_startup_state = udB.get_key("STARTUP_STATE")
    if prev_startup_state not in {"first_run", "clean_quit", "crash", "running"}:
        prev_startup_state = "first_run"
        udB.set_key("STARTUP_STATE", prev_startup_state)
    set_startup_state("running")

    BOT_MODE = udB.get_key("BOTMODE")
    DUAL_MODE = udB.get_key("DUAL_MODE")

    USER_MODE = udB.get_key("USER_MODE")
    if USER_MODE:
        DUAL_MODE = False

    if BOT_MODE:
        if DUAL_MODE:
            udB.del_key("DUAL_MODE")
            DUAL_MODE = False
        ultroid_bot = None

        if not udB.get_key("BOT_TOKEN"):
            LOGS.warning(
                '"BOT_TOKEN" not Found! Continuing with startup; bot features will stay limited until it is added.'
            )
    else:
        # Read BOT_TOKEN from .env (source of truth), not the DB. A stale
        # BOT_TOKEN in the DB from a previous autobot run would otherwise
        # block this fallback and cause asst to be instantiated as a
        # separate client that then fails to authenticate.
        _has_bot_token_env = bool(getattr(Var, "BOT_TOKEN", None))
        _has_bot_token_db = bool(udB.get_key("BOT_TOKEN"))
        if udB.get_key("SESSION") and not _has_bot_token_env:
            LOGS.info(
                "BOT_TOKEN is not set; running in USER_MODE (asst = ultroid_bot). "
                "Add BOT_TOKEN to your .env to use a separate assistant bot."
                + (f" (ignoring stale DB value: '{_has_bot_token_db}')" if _has_bot_token_db else "")
            )
            USER_MODE = True
            udB.set_key("USER_MODE", True)
            udB.del_key("BOT_TOKEN")
        try:
            session = validate_session(getattr(Var, "SESSION", None), LOGS)
        except Exception:
            session = None

        if session:
            ultroid_bot = UltroidClient(
                session,
                udB=udB,
                app_version=ultroid_version,
                device_model="Ultroid",
            )
            ultroid_bot.run_in_loop(autobot())
        elif udB.get_key("BOT_TOKEN"):
            LOGS.info("Starting in BOTMODE without userbot session")
            os.environ["BOTMODE"] = "true"
            udB.set_key("BOTMODE", True)
            BOT_MODE = True
            ultroid_bot = None
        else:
            LOGS.critical(
                '"SESSION" is invalid and "BOT_TOKEN" not Found! '
                'Please add "BOT_TOKEN" to start in "BOTMODE"'
            )
            sys.exit()

    if USER_MODE:
        asst = ultroid_bot
    else:
        bot_token = udB.get_key("BOT_TOKEN")
        if not bot_token:
            LOGS.warning(
                '"BOT_TOKEN" not Found! Assistant bot will be unavailable until it is added.'
            )
        asst = UltroidClient(StringSession(), bot_token=bot_token, udB=udB)

    assert asst is not None

    if BOT_MODE:
        ultroid_bot = asst
        if udB.get_key("OWNER_ID") and ultroid_bot is not None:
            try:
                owner_id = udB.get_key("OWNER_ID")
                if owner_id is not None:
                    setattr(
                        ultroid_bot,
                        "me",
                        ultroid_bot.run_in_loop(ultroid_bot.get_entity(owner_id)),
                    )
            except Exception as er:
                LOGS.exception(er)
    else:
        asst_me = cast(Any, asst.me)
        if ultroid_bot is not None and not asst_me.bot_inline_placeholder and asst._bot:
            ultroid_bot.run_in_loop(enable_inline(ultroid_bot, asst_me.username))

    vcClient = vc_connection(udB, ultroid_bot)

    _version_changes(udB)

    # Register graceful disconnect on process exit
    import atexit
    from ._misc.context import bind_from_globals

    def _atexit_disconnect():
        """Disconnect all Telegram clients on unexpected process exit."""
        try:
            set_startup_state("clean_quit")
        except Exception:
            pass
        for name, client in (
            ("vcClient", vcClient),
            ("ultroid_bot", ultroid_bot),
            ("asst", asst),
        ):
            if client is not None:
                try:
                    client_ = cast(Any, client)
                    client_.loop.run_until_complete(client_.disconnect())
                except Exception:
                    pass

    def _uncaught_exception_handler(exc_type, exc, tb):
        try:
            set_startup_state("crash")
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    atexit.register(_atexit_disconnect)
    sys.excepthook = _uncaught_exception_handler
    bind_from_globals()

    HNDLR = udB.get_key("HNDLR") or "."
    DUAL_HNDLR = udB.get_key("DUAL_HNDLR") or "/"
    SUDO_HNDLR = udB.get_key("SUDO_HNDLR") or HNDLR
else:
    print("pyUltroid 2022 © TeamUltroid")

    from logging import getLogger

    LOGS = getLogger("pyUltroid")

    ultroid_bot = asst = udB = vcClient = None
