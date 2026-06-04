# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.

from pathlib import Path
from typing import Protocol, cast

from pyUltroid.dB._core import LOADED  # pyright: ignore[reportUnknownVariableType]
from pyUltroid.startup.config import ESSENTIAL_PLUGINS, PLUGIN_CATEGORIES

from pyUltroid._misc._decorators import ultroid_cmd  # pyright: ignore[reportUnknownVariableType]

from . import HNDLR  # pyright: ignore[reportUnknownVariableType]

LOADED_TYPED = cast(dict[str, list[object]], LOADED)
HNDLR_TYPED = cast(str, HNDLR)
ESSENTIAL = {p for plugs in ESSENTIAL_PLUGINS.values() for p in plugs}


class _PatternMatch(Protocol):
    def group(self, index: int) -> str | None: ...


class _ListPluginsEvent(Protocol):
    pattern_match: _PatternMatch

    async def eor(self, text: str): ...


def _plugin_status(name: str) -> str:
    if name in ESSENTIAL:
        return "🔒"
    return "✅" if LOADED_TYPED.get(name) else "❌"


def _format_plugin(name: str) -> str:
    return f"{_plugin_status(name)} `{name}`"


@ultroid_cmd(pattern="list_plugins( (.*)|$)")
async def list_plugins(event: object):
    event = cast(_ListPluginsEvent, event)
    query = str((event.pattern_match.group(1) or "")).strip().lower()
    plugin_dir = Path(__file__).resolve().parent
    all_plugins = sorted(
        p.stem
        for p in plugin_dir.glob("*.py")
        if not p.stem.startswith("_")
    )

    categories = list(PLUGIN_CATEGORIES.items())
    rendered: list[str] = []

    for category, plugins in categories:
        items = [p for p in plugins if not p.startswith("_")]
        if query and query not in category.lower() and not any(query in p.lower() for p in items):
            continue
        matched = [p for p in items if p in all_plugins and (not query or query in p.lower() or query in category.lower())]
        if not matched:
            continue
        rendered.append(f"**{category.title()}**")
        rendered.extend(f"• {_format_plugin(p)}" for p in sorted(matched))
        rendered.append("")

    categorized = {x for vals in PLUGIN_CATEGORIES.values() for x in vals}
    uncategorized: list[str] = [p for p in all_plugins if p not in categorized]
    uncategorized = [p for p in uncategorized if not query or query in p.lower() or query in "other"]
    if uncategorized:
        rendered.append("**Other**")
        rendered.extend(f"• {_format_plugin(p)}" for p in uncategorized)

    if not rendered:
        return await event.eor(f"No plugins found for `{query or 'all'}`.")

    text = "\n".join(rendered).strip()
    text += f"\n\n`✅ loaded` `❌ unloaded` `🔒 essential`\nUse `{HNDLR_TYPED}list_plugins admin` to filter."
    await event.eor(text)
