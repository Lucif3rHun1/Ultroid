# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/TeamUltroid/pyUltroid/blob/main/LICENSE>.

import ast
import os
import subprocess
import sys
import threading

from .. import run_as_module
from . import *
from .._misc.ttl_cache import TTLCache

if run_as_module:
    from ..configs import Var


Redis = MongoClient = psycopg2 = Database = None
if Var.REDIS_URI or Var.REDISHOST:
    try:
        from redis import Redis
    except ImportError:
        LOGS.info("Installing 'redis' for database.")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "redis", "hiredis"], check=False)
        from redis import Redis
elif Var.MONGO_URI:
    try:
        from pymongo import MongoClient
    except ImportError:
        LOGS.info("Installing 'pymongo' for database.")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pymongo[srv]"], check=False)
        from pymongo import MongoClient
elif Var.DATABASE_URL:
    try:
        import psycopg2
    except ImportError:
        LOGS.info("Installing 'pyscopg2' for database.")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "psycopg2-binary"], check=False)
        import psycopg2
else:
    try:
        from localdb import Database
    except ImportError:
        LOGS.info("Using local file as database.")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "localdb.json"], check=False)
        from localdb import Database

# --------------------------------------------------------------------------------------------- #


class _BaseDatabase:
    def __init__(self, *args, **kwargs):
        self._cache = TTLCache(maxsize=2048, ttl=0)
        self._cache_lock = threading.RLock()

    def get_key(self, key):
        with self._cache_lock:
            cached = self._cache.get(key, _MISSING := object())
            if cached is not _MISSING:
                return cached
        value = self._get_data(key)
        with self._cache_lock:
            self._cache.set(key, value)
        return value

    def re_cache(self):
        with self._cache_lock:
            self._cache.clear()
        for key in self.keys():
            self.get_key(key)

    def ping(self):
        return 1

    @property
    def usage(self):
        return 0

    def keys(self):
        return []

    def del_key(self, key):
        with self._cache_lock:
            self._cache.delete(key)
        self.delete(key)
        return True

    def _get_data(self, key=None, data=None):
        if key:
            data = self.get(str(key))
        if data and isinstance(data, str):
            try:
                data = ast.literal_eval(data)
            except BaseException:
                pass
        return data

    def set_key(self, key, value, cache_only=False):
        value = self._get_data(data=value)
        with self._cache_lock:
            self._cache.set(key, value)
        if cache_only:
            return
        return self.set(str(key), str(value))

    def rename(self, key1, key2):
        _ = self.get_key(key1)
        if _:
            self.del_key(key1)
            self.set_key(key2, _)
            return 0
        return 1


class MongoDB(_BaseDatabase):
    def __init__(self, key, dbname="UltroidDB"):
        self.dB = MongoClient(
            key,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
            retryWrites=True,
            appname="pyUltroid",
        )
        self.db = self.dB[dbname]
        super().__init__()

    def __repr__(self):
        return f"<Ultroid.MonGoDB\n -total_keys: {len(self.keys())}\n>"

    @property
    def name(self):
        return "Mongo"

    @property
    def usage(self):
        return self.db.command("dbstats")["dataSize"]

    def ping(self):
        if self.dB.server_info():
            return True

    def keys(self):
        return self.db.list_collection_names()

    def set(self, key, value):
        if key in self.keys():
            self.db[key].replace_one({"_id": key}, {"value": str(value)})
        else:
            self.db[key].insert_one({"_id": key, "value": str(value)})
        return True

    def delete(self, key):
        self.db.drop_collection(key)

    def get(self, key):
        if x := self.db[key].find_one({"_id": key}):
            return x["value"]

    def flushall(self):
        self.dB.drop_database("UltroidDB")
        self._cache.clear()
        return True


# --------------------------------------------------------------------------------------------- #

# Thanks to "Akash Pattnaik" / @BLUE-DEVIL1134
# for SQL Implementation in Ultroid.
#
# Please use https://elephantsql.com/ !


import re

def _validate_sql_identifier(name: str) -> str:
    """
    Validate and sanitize SQL identifier (column/table name).
    Only allows alphanumeric and underscore, must start with letter or underscore.
    Prevents SQL injection via identifier interpolation.
    """
    if not name:
        raise ValueError("Empty identifier")
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    # Prevent SQL keywords (basic list)
    reserved = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE',
                'TABLE', 'COLUMN', 'INDEX', 'WHERE', 'FROM', 'JOIN', 'UNION',
                'VALUES', 'SET', 'KEY', 'PRIMARY', 'FOREIGN', 'REFERENCES',
                'DEFAULT', 'NULL', 'NOT', 'AND', 'OR', 'ORDER', 'GROUP', 'BY',
                'LIMIT', 'OFFSET', 'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX'}
    if name.upper() in reserved:
        raise ValueError(f"Reserved SQL keyword: {name}")
    return name


class SqlDB(_BaseDatabase):
    def __init__(self, url):
        self._url = url
        self._connection = None
        self._cursor = None
        try:
            self._connection = psycopg2.connect(
                dsn=url,
                connect_timeout=5,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=3,
            )
            self._connection.autocommit = True
            self._cursor = self._connection.cursor()
            self._cursor.execute(
                "CREATE TABLE IF NOT EXISTS Ultroid (ultroidCli varchar(70))"
            )
        except Exception as error:
            LOGS.exception(error)
            LOGS.info("Invaid SQL Database")
            if self._connection:
                self._connection.close()
            sys.exit()
        super().__init__()

    @property
    def name(self):
        return "SQL"

    @property
    def usage(self):
        self._cursor.execute(
            "SELECT pg_size_pretty(pg_relation_size('Ultroid')) AS size"
        )
        data = self._cursor.fetchall()
        return int(data[0][0].split()[0])

    def keys(self):
        self._cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name  = 'ultroid'"
        )  # case sensitive
        data = self._cursor.fetchall()
        return [_[0] for _ in data]

    def get(self, variable):
        # SECURITY: Validate column name to prevent SQL injection
        _validate_sql_identifier(variable)
        try:
            # Column names cannot be parameterized, but we validated them
            self._cursor.execute(f"SELECT {variable} FROM Ultroid")
        except psycopg2.errors.UndefinedColumn:
            return None
        data = self._cursor.fetchall()
        if not data:
            return None
        if len(data) >= 1:
            for i in data:
                if i[0]:
                    return i[0]

    def set(self, key, value):
        # SECURITY: Validate column name to prevent SQL injection
        _validate_sql_identifier(key)
        try:
            # Column names cannot be parameterized, but we validated them
            self._cursor.execute(f"ALTER TABLE Ultroid DROP COLUMN IF EXISTS {key}")
        except (psycopg2.errors.UndefinedColumn, psycopg2.errors.SyntaxError):
            pass
        except BaseException as er:
            LOGS.exception(er)
        self._cache.update({key: value})
        # Column names cannot be parameterized, but we validated them
        self._cursor.execute(f"ALTER TABLE Ultroid ADD {key} TEXT")
        # Use parameterized query for VALUES
        self._cursor.execute(f"INSERT INTO Ultroid ({key}) values (%s)", (str(value),))
        return True

    def delete(self, key):
        # SECURITY: Validate column name to prevent SQL injection
        _validate_sql_identifier(key)
        try:
            # Column names cannot be parameterized, but we validated them
            self._cursor.execute(f"ALTER TABLE Ultroid DROP COLUMN {key}")
        except psycopg2.errors.UndefinedColumn:
            return False
        return True

    def flushall(self):
        self._cache.clear()
        self._cursor.execute("DROP TABLE Ultroid")
        self._cursor.execute(
            "CREATE TABLE IF NOT EXISTS Ultroid (ultroidCli varchar(70))"
        )
        return True


# --------------------------------------------------------------------------------------------- #


class RedisDB(_BaseDatabase):
    def __init__(
        self,
        host,
        port,
        password,
        platform="",
        logger=LOGS,
        *args,
        **kwargs,
    ):
        if host and ":" in host:
            spli_ = host.split(":")
            host = spli_[0]
            port = int(spli_[-1])
            if host.startswith("http"):
                logger.error("Your REDIS_URI should not start with http !")
                import sys

                sys.exit()
        elif not host or not port:
            logger.error("Port Number not found")
            import sys

            sys.exit()
        kwargs["host"] = host
        kwargs["password"] = password
        kwargs["port"] = port

        if platform.lower() == "qovery" and not host:
            var, hash_, host, password = "", "", "", ""
            for vars_ in os.environ:
                if vars_.startswith("QOVERY_REDIS_") and vars_.endswith("_HOST"):
                    var = vars_
            if var:
                hash_ = var.split("_", maxsplit=2)[1].split("_")[0]
            if hash_:
                kwargs["host"] = os.environ.get(f"QOVERY_REDIS_{hash_}_HOST")
                kwargs["port"] = os.environ.get(f"QOVERY_REDIS_{hash_}_PORT")
                kwargs["password"] = os.environ.get(f"QOVERY_REDIS_{hash_}_PASSWORD")
        self.db = Redis(**kwargs)
        self.set = self.db.set
        self.get = self.db.get
        self.keys = self.db.keys
        self.delete = self.db.delete
        super().__init__()

    @property
    def name(self):
        return "Redis"

    @property
    def usage(self):
        return sum(self.db.memory_usage(x) for x in self.keys())


# --------------------------------------------------------------------------------------------- #


class LocalDB(_BaseDatabase):
    def __init__(self):
        self.db = Database("ultroid")
        self.get = self.db.get
        self.set = self.db.set
        self.delete = self.db.delete
        super().__init__()

    @property
    def name(self):
        return "LocalDB"

    def keys(self):
        return self._cache.keys()

    def __repr__(self):
        return f"<Ultroid.LocalDB\n -total_keys: {len(self.keys())}\n>"


def UltroidDB():
    _er = False
    from .. import HOSTED_ON, LOGS as _LOGS

    # Detect the common user trap: multiple DB URIs set at once.
    # The connection order below would silently pick one and ignore
    # the others, leading to "I switched to Mongo but my data isn't
    # there" debugging sessions. Warn loudly instead.
    _uris_set = []
    if getattr(Var, "REDIS_URI", None) or getattr(Var, "REDISHOST", None):
        _uris_set.append("REDIS")
    if getattr(Var, "MONGO_URI", None):
        _uris_set.append("MONGO")
    if getattr(Var, "DATABASE_URL", None):
        _uris_set.append("POSTGRES")
    if len(_uris_set) > 1:
        _LOGS.warning(
            "Multiple DB URIs set in .env (%s). The first match in the "
            "if/elif chain below wins; the others will be ignored. "
            "Clear all but one from your .env to avoid data going to the "
            "wrong backend.",
            ", ".join(_uris_set),
        )

    try:
        if Redis and (Var.REDIS_URI or Var.REDISHOST):
            return RedisDB(
                host=Var.REDIS_URI or Var.REDISHOST,
                password=Var.REDIS_PASSWORD or Var.REDISPASSWORD,
                port=Var.REDISPORT,
                platform=HOSTED_ON,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
                retry_on_timeout=True,
            )
        elif MongoClient:
            return MongoDB(Var.MONGO_URI)
        elif psycopg2:
            return SqlDB(Var.DATABASE_URL)
        else:
            LOGS.critical(
                "No DB requirement fullfilled!\nPlease install redis, mongo or sql dependencies...\nTill then using local file as database."
            )
            return LocalDB()
    except BaseException as err:
        LOGS.exception(err)
    exit()


# --------------------------------------------------------------------------------------------- #
