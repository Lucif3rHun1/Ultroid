"""Startup-time configuration validation.

Pure functions that take a flat dict (the env) and return a list of
``ValidationError`` describing what's wrong. We do not raise — the
operator may be intentionally running an incomplete config (e.g. to
test the launcher itself). We log warnings and let the rest of the
startup flow proceed.

The validator runs in ``pyUltroid.__init__`` after ``load_env`` /
``update_envs`` and before any client is constructed. Catching
problems here means the bot doesn't spend 30 seconds connecting to
Telegram only to die on a bad ``API_ID``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence
from urllib.parse import urlparse


@dataclass(frozen=True)
class ValidationError:
    key: str
    value: object
    reason: str

    def __str__(self) -> str:
        return f"{self.key}={self.value!r}: {self.reason}"


_API_ID = re.compile(r"^\d{1,10}$")
_HEX = re.compile(r"^[0-9a-fA-F]{32,64}$")
_SESSION_BASE64_URL_SAFE = re.compile(r"^[A-Za-z0-9_\-]{8,}={0,2}\Z")
_BOT_TOKEN = re.compile(r"^\d{8,12}:[A-Za-z0-9_\-]{30,}$")


def _is_int_str(s: object) -> bool:
    return isinstance(s, str) and bool(_API_ID.match(s))


def _looks_like_session(s: object) -> bool:
    if not isinstance(s, str) or len(s) < 16:
        return False
    if _SESSION_BASE64_URL_SAFE.match(s) is None:
        return False
    return True


def _looks_like_bot_token(s: object) -> bool:
    return isinstance(s, str) and bool(_BOT_TOKEN.match(s))


def _looks_like_url(s: object, *, schemes: Sequence[str]) -> bool:
    if not isinstance(s, str) or not s:
        return False
    try:
        u = urlparse(s)
    except ValueError:
        return False
    if u.scheme not in schemes:
        return False
    if not u.netloc:
        return False
    return True


def validate_env(env: Mapping[str, object]) -> list[ValidationError]:
    """Return a list of problems with *env*; empty list means OK."""
    errs: list[ValidationError] = []

    api_id = env.get("API_ID")
    if api_id is not None and not _is_int_str(api_id):
        errs.append(ValidationError("API_ID", api_id, "must be a string of digits"))

    api_hash = env.get("API_HASH")
    if api_hash is not None and isinstance(api_hash, str):
        if not api_hash or len(api_hash) < 16:
            errs.append(ValidationError("API_HASH", api_hash, "looks too short"))
        elif api_hash.startswith("your_") or "placeholder" in api_hash.lower():
            errs.append(ValidationError("API_HASH", api_hash, "still a placeholder"))

    has_session = "SESSION" in env and env["SESSION"]
    has_bot_token = "BOT_TOKEN" in env and env["BOT_TOKEN"]
    if not has_session and not has_bot_token:
        errs.append(ValidationError("SESSION/BOT_TOKEN", None, "neither is set"))
    if has_session and not _looks_like_session(env["SESSION"]):
        errs.append(ValidationError(
            "SESSION", "<redacted>",
            "does not look like a Telethon string session",
        ))
    if has_bot_token and not _looks_like_bot_token(env["BOT_TOKEN"]):
        errs.append(ValidationError(
            "BOT_TOKEN", "<redacted>",
            "does not match Telegram bot token format (id:secret)",
        ))

    db_present = sum(
        1 for k in ("REDIS_URI", "MONGO_URI", "DATABASE_URL") if env.get(k)
    )
    if db_present == 0:
        errs.append(ValidationError(
            "REDIS_URI/MONGO_URI/DATABASE_URL", None,
            "no database URI is set; bot will fall back to local file",
        ))
    if db_present > 1:
        errs.append(ValidationError(
            "<db>", None,
            "more than one database URI is set; the first match wins (Redis > Mongo > SQL)",
        ))

    redis = env.get("REDIS_URI")
    if redis and not _looks_like_url(redis, schemes=("redis", "rediss")):
        errs.append(ValidationError("REDIS_URI", redis, "not a redis:// URL"))

    mongo = env.get("MONGO_URI")
    if mongo and not _looks_like_url(mongo, schemes=("mongodb", "mongodb+srv")):
        errs.append(ValidationError("MONGO_URI", mongo, "not a mongodb:// URL"))

    db_url = env.get("DATABASE_URL")
    if db_url and not _looks_like_url(db_url, schemes=("postgres", "postgresql")):
        errs.append(ValidationError("DATABASE_URL", db_url, "not a postgres:// URL"))

    log_ch = env.get("LOG_CHANNEL")
    if log_ch is not None and not (isinstance(log_ch, int) or (isinstance(log_ch, str) and (log_ch.lstrip("-").isdigit() or log_ch == "me"))):
        errs.append(ValidationError(
            "LOG_CHANNEL", log_ch,
            "should be an integer chat id, '-100...' channel id, or 'me'",
        ))

    heroku_app = env.get("HEROKU_APP_NAME")
    heroku_key = env.get("HEROKU_API")
    if (heroku_app and not heroku_key) or (heroku_key and not heroku_app):
        errs.append(ValidationError(
            "HEROKU_APP_NAME/HEROKU_API", None,
            "both must be set together; one without the other is rejected by heroku3",
        ))

    return errs


def report(errors: Sequence[ValidationError], log) -> int:
    """Log each error as a WARNING. Returns the count."""
    if not errors:
        return 0
    for err in errors:
        log.warning("Config validation: %s", err)
    log.warning(
        "Config validation: %d issue(s) found. Bot may not start correctly.",
        len(errors),
    )
    return len(errors)
