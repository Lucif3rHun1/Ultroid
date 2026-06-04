# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.

import re

from telethon import Button

from pyUltroid.startup.config import (
    PLUGIN_CATEGORIES,
    get_plugin_config,
    get_startup_state,
    set_plugin_config,
    set_startup_state,
)

from . import *

# Category display mapping: display_name -> config_key
CATEGORY_MAP = {
    "⚙️ Admin": "admin",
    "🎨 Media": "media",
    "🔧 Tools": "tools",
    "🎮 Games": "fun",
    "💬 Social": "social",
    "🖥 System": "system",
    "🚀 Advanced": "advanced",
}


def _build_category_buttons():
    """Build inline keyboard with category buttons showing plugin counts."""
    plugin_config = get_plugin_config()
    buttons = []
    row = []
    for idx, (display, key) in enumerate(CATEGORY_MAP.items()):
        plugins = PLUGIN_CATEGORIES.get(key, [])
        active = plugin_config.get(key, [])
        count = len(active)
        total = len(plugins)
        label = f"{display}\n{count}/{total}"
        row.append(Button.inline(label, data=f"pwizard_cat_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append(
        [
            Button.inline("✅ Done", data="pwizard_done"),
            Button.inline("🔄 Reset All", data="pwizard_reset"),
        ]
    )
    return buttons


def _build_category_plugins(category_key):
    """Build inline keyboard with toggle buttons for plugins in a category."""
    plugins = PLUGIN_CATEGORIES.get(category_key, [])
    plugin_config = get_plugin_config()
    active = set(plugin_config.get(category_key, []))
    buttons = []
    row = []
    for idx, plugin_name in enumerate(plugins):
        status = "✅" if plugin_name in active else "⬜"
        row.append(
            Button.inline(
                f"{status} {plugin_name}",
                data=f"pwizard_toggle_{category_key}_{plugin_name}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    # Select all / Deselect all
    buttons.append(
        [
            Button.inline("✅ Select All", data=f"pwizard_selectall_{category_key}"),
            Button.inline("⬜ Deselect All", data=f"pwizard_deselectall_{category_key}"),
        ]
    )
    buttons.append([Button.inline("« Back to Categories", data="pwizard_menu")])
    return buttons


async def send_wizard(event_or_client, chat_id):
    """Send the plugin wizard welcome message with category keyboard."""
    plugin_config = get_plugin_config()
    total_active = sum(len(v) for v in plugin_config.values())
    total_available = sum(len(v) for v in PLUGIN_CATEGORIES.values())
    welcome = (
        f"👋 **Welcome to Ultroid Plugin Setup!**\n\n"
        f"Choose which plugin categories to enable.\n"
        f"Currently active: **{total_active}/{total_available}** plugins\n\n"
        f"Tap a category to configure its plugins."
    )
    await event_or_client.send_message(
        chat_id,
        welcome,
        buttons=_build_category_buttons(),
    )


# ─────────────────────────────────────────────
# /config plugins - triggers wizard on demand
# ─────────────────────────────────────────────


@asst_cmd(pattern="config plugins", owner=True)
async def config_plugins_cmd(event):
    """Handle /config plugins command."""
    if event.sender_id != OWNER_ID:
        return
    await send_wizard(event, event.chat_id)


# ─────────────────────────────────────────────
# Auto-send wizard on first startup
# ─────────────────────────────────────────────


@asst_cmd(pattern="start( (.*)|$)", forwards=False, func=lambda x: not x.is_group)
async def _wizard_startup_hook(event):
    """
    Hook into the start command to send wizard on first run.
    Only triggers for the owner, only on first_run state.
    """
    if event.sender_id != OWNER_ID:
        return
    if get_startup_state() != "first_run":
        return
    # Mark as configured so we don't spam on every restart
    set_startup_state("configured")
    await send_wizard(event, event.chat_id)


# ─────────────────────────────────────────────
# Callback: Main menu
# ─────────────────────────────────────────────


@callback("pwizard_menu", owner=True)
async def pwizard_menu(event):
    """Show the main category selection menu."""
    plugin_config = get_plugin_config()
    total_active = sum(len(v) for v in plugin_config.values())
    total_available = sum(len(v) for v in PLUGIN_CATEGORIES.values())
    text = (
        f"👋 **Plugin Setup**\n\n"
        f"Currently active: **{total_active}/{total_available}** plugins\n\n"
        f"Tap a category to configure its plugins."
    )
    await event.edit(text, buttons=_build_category_buttons())


# ─────────────────────────────────────────────
# Callback: View category plugins
# ─────────────────────────────────────────────


@callback(re.compile(r"pwizard_cat_(.+)"), owner=True)
async def pwizard_category(event):
    """Show plugins within a selected category."""
    cat_key = event.data_match.group(1).decode("utf-8")
    plugins = PLUGIN_CATEGORIES.get(cat_key, [])
    plugin_config = get_plugin_config()
    active = set(plugin_config.get(cat_key, []))
    display_name = cat_key.capitalize()
    for d, k in CATEGORY_MAP.items():
        if k == cat_key:
            display_name = d
            break
    text = (
        f"**{display_name}** — {len(active)}/{len(plugins)} active\n\n"
        f"Toggle plugins on/off. Changes apply on next restart."
    )
    await event.edit(text, buttons=_build_category_plugins(cat_key))


# ─────────────────────────────────────────────
# Callback: Toggle individual plugin
# ─────────────────────────────────────────────


@callback(re.compile(r"pwizard_toggle_(.+)_(.+)"), owner=True)
async def pwizard_toggle(event):
    """Toggle a single plugin on/off."""
    cat_key = event.data_match.group(1).decode("utf-8")
    plugin_name = event.data_match.group(2).decode("utf-8")
    plugin_config = get_plugin_config()
    active = list(plugin_config.get(cat_key, []))
    if plugin_name in active:
        active.remove(plugin_name)
    else:
        active.append(plugin_name)
    plugin_config[cat_key] = active
    set_plugin_config(plugin_config)
    # Rebuild the category view
    plugins = PLUGIN_CATEGORIES.get(cat_key, [])
    active_set = set(active)
    display_name = cat_key.capitalize()
    for d, k in CATEGORY_MAP.items():
        if k == cat_key:
            display_name = d
            break
    text = (
        f"**{display_name}** — {len(active_set)}/{len(plugins)} active\n\n"
        f"Toggle plugins on/off. Changes apply on next restart."
    )
    await event.edit(text, buttons=_build_category_plugins(cat_key))


# ─────────────────────────────────────────────
# Callback: Select all in category
# ─────────────────────────────────────────────


@callback(re.compile(r"pwizard_selectall_(.+)"), owner=True)
async def pwizard_select_all(event):
    """Enable all plugins in a category."""
    cat_key = event.data_match.group(1).decode("utf-8")
    plugin_config = get_plugin_config()
    plugin_config[cat_key] = list(PLUGIN_CATEGORIES.get(cat_key, []))
    set_plugin_config(plugin_config)
    plugins = PLUGIN_CATEGORIES.get(cat_key, [])
    display_name = cat_key.capitalize()
    for d, k in CATEGORY_MAP.items():
        if k == cat_key:
            display_name = d
            break
    text = (
        f"**{display_name}** — {len(plugins)}/{len(plugins)} active\n\n"
        f"Toggle plugins on/off. Changes apply on next restart."
    )
    await event.edit(text, buttons=_build_category_plugins(cat_key))


# ─────────────────────────────────────────────
# Callback: Deselect all in category
# ─────────────────────────────────────────────


@callback(re.compile(r"pwizard_deselectall_(.+)"), owner=True)
async def pwizard_deselect_all(event):
    """Disable all plugins in a category."""
    cat_key = event.data_match.group(1).decode("utf-8")
    plugin_config = get_plugin_config()
    plugin_config[cat_key] = []
    set_plugin_config(plugin_config)
    plugins = PLUGIN_CATEGORIES.get(cat_key, [])
    display_name = cat_key.capitalize()
    for d, k in CATEGORY_MAP.items():
        if k == cat_key:
            display_name = d
            break
    text = (
        f"**{display_name}** — 0/{len(plugins)} active\n\n"
        f"Toggle plugins on/off. Changes apply on next restart."
    )
    await event.edit(text, buttons=_build_category_plugins(cat_key))


# ─────────────────────────────────────────────
# Callback: Done / Finish wizard
# ─────────────────────────────────────────────


@callback("pwizard_done", owner=True)
async def pwizard_done(event):
    """Finish the wizard and show summary."""
    plugin_config = get_plugin_config()
    total_active = sum(len(v) for v in plugin_config.values())
    total_available = sum(len(v) for v in PLUGIN_CATEGORIES.values())
    summary_lines = []
    for display, key in CATEGORY_MAP.items():
        active = plugin_config.get(key, [])
        if active:
            summary_lines.append(f"  • {display}: {', '.join(active)}")
    summary = "\n".join(summary_lines) if summary_lines else "  No plugins selected."
    text = (
        f"✅ **Plugin Setup Complete!**\n\n"
        f"Active: **{total_active}/{total_available}** plugins\n\n"
        f"{summary}\n\n"
        f"Changes apply on next restart.\n"
        f"Run `/config plugins` anytime to reconfigure."
    )
    await event.edit(
        text,
        buttons=[
            [Button.inline("« Back to Categories", data="pwizard_menu")],
        ],
        link_preview=False,
    )


# ─────────────────────────────────────────────
# Callback: Reset all selections
# ─────────────────────────────────────────────


@callback("pwizard_reset", owner=True)
async def pwizard_reset(event):
    """Reset all plugin selections to essential defaults."""
    from pyUltroid.startup.config import ESSENTIAL_PLUGINS

    set_plugin_config(dict(ESSENTIAL_PLUGINS))
    plugin_config = get_plugin_config()
    total_active = sum(len(v) for v in plugin_config.values())
    total_available = sum(len(v) for v in PLUGIN_CATEGORIES.values())
    text = (
        f"🔄 **Reset to defaults!**\n\n"
        f"Active: **{total_active}/{total_available}** plugins (essentials only)\n\n"
        f"Tap a category to customize further."
    )
    await event.edit(text, buttons=_build_category_buttons())
