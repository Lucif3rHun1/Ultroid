PLUGIN_CONFIG_KEY = "PLUGIN_CONFIG"
STARTUP_STATE_KEY = "STARTUP_STATE"


class _DB:
    def get_key(self, key: str):
        del key

    def set_key(self, key: str, value: object):
        del key, value

ESSENTIAL_PLUGINS = {
    "core": ["_help", "_inline", "_userlogs", "_wspr", "_ultroid", "bot", "core"],
    "tools": ["tools", "database"],
    "admin": [],
    "media": [],
    "system": [],
}


PLUGIN_CATEGORIES = {
    "core": ["_help", "_inline", "_ultroid", "_userlogs", "_wspr", "bot", "core"],
    "admin": [
        "admintools",
        "autoban",
        "blacklist",
        "channelhacks",
        "forcesubscribe",
        "locks",
        "mute",
        "pmpermit",
        "sudo",
        "warn",
    ],
    "tools": ["button", "calculator", "converter", "misc", "notes", "qrcode", "resize", "search", "tools", "utilities", "words", "ziptools"],
    "media": [
        "audiotools",
        "beautify",
        "compressor",
        "downloadupload",
        "fileshare",
        "giftools",
        "gdrive",
        "imagetools",
        "mediatools",
        "pdftools",
        "stickertools",
        "videotools",
        "vctools",
        "webupload",
        "youtube",
        "autopic",
        "logo",
        "profile",
        "stories",
        "unsplash",
        "writer",
    ],
    "system": ["_chatactions", "cleanaction", "database", "devtools", "globaltools", "usage", "variables"],
    "social": ["afk", "asstcmd", "broadcast", "chatbot", "chats", "echo", "greetings", "polls", "schedulemsg", "tag", "twitter"],
    "heavy": ["aiwrapper", "specialtools"],
    "filters": ["antiflood", "filter", "nsfwfilter", "profanityfilter"],
    "fun": ["extra", "fakeaction", "fontgen", "glitch", "nightmode", "other", "snips", "weather"],
    "advanced": [],
}


def get_plugin_config() -> dict[str, list[str]]:
    from .. import udB

    assert udB is not None
    db: _DB = udB
    return db.get_key(PLUGIN_CONFIG_KEY) or ESSENTIAL_PLUGINS


def set_plugin_config(config: dict[str, list[str]]):
    from .. import udB

    assert udB is not None
    db: _DB = udB
    return db.set_key(PLUGIN_CONFIG_KEY, config)


def get_startup_state():
    from .. import udB

    assert udB is not None
    db: _DB = udB
    return db.get_key(STARTUP_STATE_KEY) or "first_run"


def set_startup_state(state: str):
    from .. import udB

    assert udB is not None
    db: _DB = udB
    return db.set_key(STARTUP_STATE_KEY, state)
