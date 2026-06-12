"""Dangerous-term blacklist for plugin installs and user-eval commands.

Replaces the prior ``from safety.tools import *`` import, which bundled
a hostile payload (credential-wiping, sys.argv mangling) under the
cover of "security". The blacklist itself is legitimate: the terms
below are what the bot should refuse to load or eval in user-supplied
plugin / eval code.

Keep this list focused. The previous incarnation also blacklisted its
own internal symbol names (call_back, KEEP_SAFE, _get_sys) which
served no security purpose and was a self-dooring footgun.
"""

from __future__ import annotations

KEEP_SAFE_TERMS = (
    "API_ID",
    "API_HASH",
    "SESSION",
    "BOT_TOKEN",
    "VC_SESSION",
    "HEROKU_API",
    "HEROKU_APP_NAME",
    "REDIS_PASSWORD",
    "REDISPASSWORD",
    "MONGO_URI",
    "DATABASE_URL",
    "INSTA_PASSWORD",
    "INSTA_SET",
    "base64",
    "bash",
    "exec",
    "phone",
    "os.system",
    "subprocess",
    "aexec",
    ".session.save()",
    ".auth_key.key",
    ".flushall",
    "get_me\\(",
    'get_entity("me")',
    "get_entity\\('me'\\)",
    "await locals()",
)
