# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.


from . import get_help

__doc__ = get_help("help_core")


import os
import importlib
import sys

from pyUltroid.startup.loader import load_addons

from pyUltroid.startup.config import (
    ESSENTIAL_PLUGINS,
    PLUGIN_CATEGORIES,
    get_plugin_config,
    set_plugin_config,
)

from . import OWNER_ID, LOGS, async_searcher, eod, get_string, safeinstall, ultroid_cmd, un_plug


async def _owner_only(event):
    if event.sender_id != OWNER_ID:
        await event.eor("⚠️ This command is restricted to the bot owner.", time=5)
        return True
    return False


@ultroid_cmd(pattern="install", fullsudo=True)
async def install(event):
    if await _owner_only(event):
        return
    await safeinstall(event)


@ultroid_cmd(
    pattern=r"unload( (.*)|$)",
)
async def unload(event):
    if await _owner_only(event):
        return
    shortname = event.pattern_match.group(1).strip()
    if not shortname:
        await event.eor(get_string("core_9"))
        return
    lsd = os.listdir("addons")
    zym = f"{shortname}.py"
    if zym in lsd:
        try:
            un_plug(shortname)
            await event.eor(f"**Uɴʟᴏᴀᴅᴇᴅ** `{shortname}` **Sᴜᴄᴄᴇssғᴜʟʟʏ.**", time=3)
        except Exception as ex:
            LOGS.exception(ex)
            return await event.eor(str(ex))
    elif zym in os.listdir("plugins"):
        return await event.eor(get_string("core_11"), time=3)
    else:
        await event.eor(f"**No Plugin Named** `{shortname}`", time=3)


@ultroid_cmd(
    pattern=r"uninstall( (.*)|$)",
)
async def uninstall(event):
    if await _owner_only(event):
        return
    shortname = event.pattern_match.group(1).strip()
    if not shortname:
        await event.eor(get_string("core_13"))
        return
    lsd = os.listdir("addons")
    zym = f"{shortname}.py"
    if zym in lsd:
        try:
            un_plug(shortname)
            await event.eor(f"**Uninstalled** `{shortname}` **successfully.**", time=3)
            os.remove(f"addons/{shortname}.py")
        except Exception as ex:
            return await event.eor(str(ex))
    elif zym in os.listdir("plugins"):
        return await event.eor(get_string("core_15"), time=3)
    else:
        return await event.eor(f"**No Plugin Named** `{shortname}`", time=3)


@ultroid_cmd(
    pattern=r"load( (.*)|$)",
    fullsudo=True,
)
async def load(event):
    if await _owner_only(event):
        return
    shortname = event.pattern_match.group(1).strip()
    if not shortname:
        await event.eor(get_string("core_16"))
        return
    try:
        try:
            un_plug(shortname)
        except BaseException:
            pass
        load_addons(f"addons/{shortname}.py")
        await event.eor(get_string("core_17").format(shortname), time=3)
    except Exception as e:
        LOGS.exception(e)
        await eod(
            event,
            get_string("core_18").format(shortname, e),
            time=3,
        )


@ultroid_cmd(pattern=r"reload_plugin( (.*)|$)", fullsudo=True)
async def reload_plugin(event):
    if await _owner_only(event):
        return
    shortname = event.pattern_match.group(1).strip()
    if not shortname:
        await event.eor(get_string("core_16"))
        return

    zym = f"{shortname}.py"
    addon_path = f"addons/{zym}"
    if zym not in os.listdir("addons"):
        if zym in os.listdir("plugins"):
            return await event.eor(get_string("core_11"), time=3)
        return await event.eor(f"**No Plugin Named** `{shortname}`", time=3)

    module_key = f"addons.{shortname}"
    try:
        if module_key not in sys.modules:
            load_addons(addon_path)
        else:
            un_plug(shortname)
            importlib.reload(sys.modules[module_key])
        await event.eor(f"**Reloaded** `{shortname}` **successfully.**", time=3)
    except Exception as ex:
        LOGS.exception(ex)
        return await event.eor(f"**Reload failed** `{shortname}`\n`{ex}`", time=5)


@ultroid_cmd(pattern="getaddons( (.*)|$)", fullsudo=True)
async def get_the_addons_lol(event):
    if await _owner_only(event):
        return
    thelink = event.pattern_match.group(1).strip()
    xx = await event.eor(get_string("com_1"))
    fool = get_string("gas_1")
    if thelink is None:
        return await xx.eor(fool, time=10)
    split_thelink = thelink.split("/")
    if not ("raw" in thelink and thelink.endswith(".py")):
        return await xx.eor(fool, time=10)
    name_of_it = split_thelink[-1]
    plug = await async_searcher(thelink)
    fil = f"addons/{name_of_it}"
    await xx.edit("Packing the codes...")
    with open(fil, "w", encoding="utf-8") as uult:
        uult.write(str(plug))
    await xx.edit("Packed. Now loading the plugin..")
    shortname = name_of_it.split(".")[0]
    try:
        load_addons(fil)
        await xx.eor(get_string("core_17").format(shortname), time=15)
    except Exception as e:
        LOGS.exception(e)
        await eod(
            xx,
            get_string("core_18").format(shortname, e),
            time=3,
        )


@ultroid_cmd(pattern=r"unload_plugin( (.*)|$)", fullsudo=True)
async def unload_plugin(event):
    if await _owner_only(event):
        return
    args = event.pattern_match.group(1).strip()
    if not args:
        return await event.eor("**Provide plugin name(s) to unload.**", time=3)

    plugins_to_unload = args.split()

    essential = set()
    for plugins in ESSENTIAL_PLUGINS.values():
        essential.update(plugins)

    unloaded = []
    refused = []
    not_found = []

    for plugin_name in plugins_to_unload:
        if plugin_name in essential:
            refused.append(plugin_name)
            continue

        from pyUltroid.fns.helper import get_plugin_handlers

        handlers = get_plugin_handlers(plugin_name)
        if not handlers:
            not_found.append(plugin_name)
            continue

        from pyUltroid.fns.helper import remove_plugin_handlers

        if remove_plugin_handlers(plugin_name):
            unloaded.append(plugin_name)

        config = get_plugin_config() or {}
        updated = False
        for _cat, plugin_list in list(config.items()):
            if isinstance(plugin_list, list) and plugin_name in plugin_list:
                plugin_list.remove(plugin_name)
                updated = True
        if updated:
            set_plugin_config(config)

    msg_parts = []
    if unloaded:
        msg_parts.append(f"**✅ Unloaded:** `{'` `'.join(unloaded)}`")
    if refused:
        msg_parts.append(f"**🔒 Essential (refused):** `{'` `'.join(refused)}`")
    if not_found:
        msg_parts.append(f"**❌ Not loaded:** `{'` `'.join(not_found)}`")

    if not msg_parts:
        msg_parts.append("**Nothing to unload.**")

    await event.eor("\n".join(msg_parts), time=5)


@ultroid_cmd(pattern=r"load_plugin( (.*)|$)", fullsudo=True)
async def load_plugin(event):
    if await _owner_only(event):
        return
    args = event.pattern_match.group(1).strip()
    if not args:
        return await event.eor(get_string("core_16"))

    plugins_to_load = args.split()
    from pyUltroid.loader import Loader
    from pyUltroid.startup.loader import _after_load

    plugin_config = get_plugin_config() or {}
    loaded = []
    failed = []
    not_found = []

    for plugin_name in plugins_to_load:
        paths = {
            "official": f"plugins/{plugin_name}.py",
            "addon": f"addons/{plugin_name}.py",
            "assistant": f"assistant/{plugin_name}.py",
            "vcbot": f"vcbot/{plugin_name}.py",
        }

        plugin_type = None
        for ptype, path in paths.items():
            if os.path.exists(path):
                plugin_type = ptype
                break

        if not plugin_type:
            not_found.append(plugin_name)
            continue

        try:
            un_plug(plugin_name)
        except BaseException:
            pass

        try:
            if plugin_type == "addon":
                load_addons(f"addons/{plugin_name}.py")
                addons = plugin_config.get("addons", [])
                if plugin_name not in addons:
                    addons.append(plugin_name)
                    plugin_config["addons"] = addons

            elif plugin_type == "official":
                mod_name = f"plugins.{plugin_name}"
                if mod_name in sys.modules:
                    del sys.modules[mod_name]
                Loader(path="plugins").load(
                    include=[plugin_name],
                    after_load=_after_load,
                )
                category = None
                for cat, plugins in PLUGIN_CATEGORIES.items():
                    if plugin_name in plugins:
                        category = cat
                        break
                if not category:
                    category = "advanced"
                cat_plugins = plugin_config.get(category, [])
                if plugin_name not in cat_plugins:
                    cat_plugins.append(plugin_name)
                    plugin_config[category] = cat_plugins

            elif plugin_type == "assistant":
                mod_name = f"assistant.{plugin_name}"
                if mod_name in sys.modules:
                    del sys.modules[mod_name]
                Loader(path="assistant").load(
                    include=[plugin_name],
                    log=False,
                    after_load=_after_load,
                )

            elif plugin_type == "vcbot":
                mod_name = f"vcbot.{plugin_name}"
                if mod_name in sys.modules:
                    del sys.modules[mod_name]
                Loader(path="vcbot", key="VCBot").load(
                    include=[plugin_name],
                    after_load=_after_load,
                )

            loaded.append(plugin_name)

        except Exception as e:
            LOGS.exception(e)
            failed.append((plugin_name, str(e)))

    if loaded:
        set_plugin_config(plugin_config)

    msg_parts = []
    if loaded:
        msg_parts.append(f"**✅ Loaded:** `{'` `'.join(loaded)}`")
    if failed:
        msg_parts.append(
            "**❌ Failed:**\n"
            + "\n".join(f"• `{name}` → `{err}`" for name, err in failed)
        )
    if not_found:
        msg_parts.append(f"**🔍 Not found:** `{'` `'.join(not_found)}`")

    if not msg_parts:
        msg_parts.append("**Nothing to load.**")

    await event.eor("\n".join(msg_parts), time=5)
