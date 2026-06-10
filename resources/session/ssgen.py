#!/usr/bin/python3
# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.

import os
from time import sleep


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_FILE = os.path.join(ROOT_DIR, ".env")

ULTROID = r"""
  _    _ _ _             _     _
 | |  | | | |           (_)   | |
 | |  | | | |_ _ __ ___  _  __| |
 | |  | | | __| '__/ _ \| |/ _  |
 | |__| | | |_| | | (_) | | (_| |
  \____/|_|\__|_|  \___/|_|\__,_|
"""


def spinner(x):
    if x == "tele":
        print("Checking if Telethon is installed...")
    else:
        print("Checking if Pyrogram is installed...")
    for _ in range(3):
        for frame in r"-\|/-\|/":
            print("\b", frame, sep="", end="", flush=True)
            sleep(0.1)


def clear_screen():
    # https://www.tutorialspoint.com/how-to-clear-screen-in-python#:~:text=In%20Python%20sometimes%20we%20have,screen%20by%20pressing%20Control%20%2B%20l%20.
    if os.name == "posix":
        os.system("clear")
    else:
        # for windows platfrom
        os.system("cls")


def load_env_file(path):
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            values[key] = value
    return values


def save_session_to_env(session_string):
    existing = []
    found = False
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8") as f:
            existing = f.readlines()
    new_lines = []
    for line in existing:
        if line.split("=", 1)[0].strip() == "SESSION":
            new_lines.append(f"SESSION={session_string}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] = new_lines[-1] + "\n"
        new_lines.append(f"SESSION={session_string}\n")
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] = new_lines[-1] + "\n"
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"SESSION saved to {ENV_FILE}")


def get_api_id_and_hash(api_id_default=None, api_hash_default=None):
    api_id_default = api_id_default if api_id_default else None
    api_hash_default = api_hash_default if api_hash_default else None
    if api_id_default is not None:
        print("Using API_ID from .env")
    else:
        print(
            "Get your API ID and API HASH from my.telegram.org or @ScrapperRoBot to proceed.\n\n",
        )
    while True:
        try:
            if api_id_default is not None:
                API_ID = int(api_id_default)
            else:
                API_ID = int(input("Please enter your API ID: "))
            break
        except ValueError:
            print("APP ID must be an integer.\nQuitting...")
            exit(1)
    if api_hash_default is not None:
        print("Using API_HASH from .env")
        API_HASH = api_hash_default
    else:
        API_HASH = input("Please enter your API HASH: ")
    if not API_HASH:
        print("API HASH must not be empty!\nQuitting...")
        exit(1)
    return API_ID, API_HASH


def telethon_session():
    try:
        spinner("tele")
        import telethon
        x = "\bFound an existing installation of Telethon...\nSuccessfully Imported.\n\n"
    except ImportError:
        print("Installing Telethon...")
        os.system("pip uninstall telethon -y && pip install -U telethon")

        x = "\bDone. Installed and imported Telethon."
    clear_screen()
    print(ULTROID)
    print(x)

    # the imports

    from telethon.errors.rpcerrorlist import (
        ApiIdInvalidError,
        PhoneNumberInvalidError,
        UserIsBotError,
    )
    from telethon.sessions import StringSession
    from telethon.sync import TelegramClient

    env_values = load_env_file(ENV_FILE)
    API_ID, API_HASH = get_api_id_and_hash(
        env_values.get("API_ID"), env_values.get("API_HASH")
    )

    # logging in
    try:
        with TelegramClient(StringSession(), API_ID, API_HASH) as ultroid:
            print("Generating a string session for •ULTROID•")
            session_string = ultroid.session.save()
            try:
                ultroid.send_message(
                    "me",
                    f"**ULTROID** `SESSION`:\n\n`{session_string}`\n\n**Do not share this anywhere!**",
                )
                print(
                    "Your SESSION has been generated. Check your Telegram saved messages!"
                )
            except UserIsBotError:
                # WARNING: Session strings are sensitive; keep them out of terminal logs.
                print("You are trying to Generate Session for your Bot's Account?")
                print("NOTE: You can't use that as User Session..")
            save_session_to_env(session_string)
            return 0
    except ApiIdInvalidError:
        print(
            "Your API ID/API HASH combination is invalid. Kindly recheck.\nQuitting..."
        )
        exit(1)
    except ValueError:
        print("API HASH must not be empty!\nQuitting...")
        exit(1)
    except PhoneNumberInvalidError:
        print("The phone number is invalid!\nQuitting...")
        exit(1)
    except Exception as er:
        print("Unexpected Error Occurred while Creating Session")
        print(er)
        print("If you think It as a Bug, Report to @UltroidSupportChat.\n\n")
        return 1


def pyro_session():
    try:
        spinner("pyro")
        from pyrogram import Client  # type: ignore[import-not-found]

        x = "\bFound an existing installation of Pyrogram...\nSuccessfully Imported.\n\n"
    except BaseException:
        print("Installing Pyrogram...")
        os.system("pip install pyrogram tgcrypto")
        x = "\bDone. Installed and imported Pyrogram."
        from pyrogram import Client  # type: ignore[import-not-found]
        
    clear_screen()
    print(ULTROID)
    print(x)

    # generate a session
    env_values = load_env_file(ENV_FILE)
    API_ID, API_HASH = get_api_id_and_hash(
        env_values.get("API_ID"), env_values.get("API_HASH")
    )
    print("Enter phone number when asked.\n\n")
    try:
        with Client(name="ultroid", api_id=API_ID, api_hash=API_HASH, in_memory=True) as pyro:
            ss = pyro.export_session_string()
            save_session_to_env(ss)
            pyro.send_message(
                "me",
                f"`{ss}`\n\nAbove is your Pyrogram Session String for @TheUltroid. **DO NOT SHARE it.**",
            )
            print("Session has been generated, saved to .env, and sent to your saved messages!")
            return 0
    except Exception as er:
        print("Unexpected error occurred while creating session, make sure to validate your inputs.")
        print(er)
        return 1


def main():
    clear_screen()
    print(ULTROID)
    try:
        type_of_ss = int(
            input(
                "\nUltroid supports both telethon as well as pyrogram sessions.\n\nWhich session do you want to generate?\n1. Telethon Session.\n2. Pyrogram Session.\n\nEnter choice:  "
            )
        )
    except Exception as e:
        print(e)
        exit(0)
    if type_of_ss == 1:
        return telethon_session()
    elif type_of_ss == 2:
        return pyro_session()
    else:
        print("Invalid choice.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
