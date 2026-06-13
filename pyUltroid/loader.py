# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/TeamUltroid/pyUltroid/blob/main/LICENSE>.

import contextlib
import glob
import os
import time
from importlib import import_module
from logging import Logger

from . import LOGS, udB
from .fns.tools import get_all_files


class Loader:
    def __init__(self, path="plugins", key="Official", logger: Logger = LOGS):
        self.path = path
        self.key = key
        self._logger = logger

    def load(
        self,
        log=True,
        func=import_module,
        include=None,
        exclude=None,
        after_load=None,
        load_all=False,
    ):
        _single = os.path.isfile(self.path)
        if include:
            if log:
                self._logger.info("Including: {}".format("• ".join(include)))
            files = glob.glob(f"{self.path}/_*.py")
            for file in include:
                path = f"{self.path}/{file}.py"
                if os.path.exists(path):
                    files.append(path)
                else:
                    self._logger.warning(
                        f"ESSENTIAL_PLUGINS requested '{file}' but {path} does not exist"
                    )
        elif _single:
            files = [self.path]
        else:
            if load_all:
                files = get_all_files(self.path, ".py")
            else:
                files = glob.glob(f"{self.path}/*.py")
            if exclude:
                for path in exclude:
                    if not path.startswith("_"):
                        with contextlib.suppress(ValueError):
                            files.remove(f"{self.path}/{path}.py")
        if log and not _single:
            self._logger.info(
                f"• Installing {self.key} Plugins || Count : {len(files)} •"
            )
        metrics = []
        for plugin in sorted(files):
            started = time.perf_counter()
            display_name = plugin.split("/")[-1].split("\\")[-1].removesuffix(".py")
            if func == import_module:
                plugin = plugin.replace(".py", "").replace("/", ".").replace("\\", ".")
            try:
                modl = func(plugin)
            except ModuleNotFoundError as er:
                modl = None
                self._logger.error(f"{plugin}: '{er.name}' not installed!")
                continue
            except Exception as exc:
                modl = None
                self._logger.error(f"pyUltroid - {self.key} - ERROR - {plugin}")
                self._logger.exception(exc)
                continue
            if _single and log:
                self._logger.info(f"Successfully Loaded {plugin}!")
            load_ms = int((time.perf_counter() - started) * 1000)
            if log:
                self._logger.info(f"Loaded {display_name} in {load_ms}ms")
            metrics.append({"plugin": display_name, "ms": load_ms, "path": self.path, "key": self.key})
            if callable(after_load):
                if func == import_module:
                    plugin = plugin.split(".")[-1]
                after_load(self, modl, plugin_name=plugin)
        if metrics:
            with contextlib.suppress(Exception):
                db = udB
                if db is not None:
                    current = db.get_key("PLUGIN_LOAD_METRICS") or []
                    if not isinstance(current, list):
                        current = []
                    current.extend(metrics)
                    db.set_key("PLUGIN_LOAD_METRICS", current)
