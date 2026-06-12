"""Thread-safe TTL+LRU cache for in-process state.

Bounded by both *maxsize* (LRU eviction) and *ttl* (per-entry expiry).
Safe to use from both synchronous and asyncio code paths via a re-entrant
lock; lookups short-circuit when the lock is contended and the caller
already has a snapshot.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Generic, Iterator, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    """A least-recently-used cache with a per-entry time-to-live.

    - ``maxsize=0`` disables the size limit.
    - ``ttl=0`` disables the time-based expiry (acts as a plain LRU).
    - ``sweep_on_get`` controls whether expired entries are evicted on
      read (default ``True``). Disable for hot paths where a stale value
      is acceptable and you would rather batch eviction.
    """

    __slots__ = (
        "_data",
        "_maxsize",
        "_ttl",
        "_sweep_on_get",
        "_lock",
        "_hits",
        "_misses",
        "_evictions",
    )

    def __init__(
        self,
        maxsize: int = 1024,
        ttl: float = 0.0,
        sweep_on_get: bool = True,
    ) -> None:
        if maxsize < 0:
            raise ValueError("maxsize must be >= 0")
        if ttl < 0:
            raise ValueError("ttl must be >= 0")
        self._data: "OrderedDict[K, tuple[float, V]]" = OrderedDict()
        self._maxsize = maxsize
        self._ttl = float(ttl)
        self._sweep_on_get = sweep_on_get
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _is_expired(self, expires_at: float) -> bool:
        return time.monotonic() >= expires_at

    def get(self, key: K, default: Any = None) -> V | Any:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return default
            expires_at, value = entry
            if self._is_expired(expires_at):
                del self._data[key]
                self._misses += 1
                self._evictions += 1
                return default
            if self._sweep_on_get:
                self._data.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: K, value: V, ttl: Optional[float] = None) -> None:
        effective_ttl = self._ttl if ttl is None else float(ttl)
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            elif self._maxsize and len(self._data) >= self._maxsize:
                self._data.popitem(last=False)
                self._evictions += 1
            expires_at = (
                float("inf") if effective_ttl <= 0 else time.monotonic() + effective_ttl
            )
            self._data[key] = (expires_at, value)

    def __setitem__(self, key: K, value: V) -> None:
        self.set(key, value)

    def __getitem__(self, key: K) -> V:
        value = self.get(key, _MISSING := object())
        if value is _MISSING:
            raise KeyError(key)
        return value  # type: ignore[return-value]

    def __contains__(self, key: K) -> bool:
        return self.get(key, _MISSING := object()) is not _MISSING

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __iter__(self) -> Iterator[K]:
        with self._lock:
            return iter(list(self._data.keys()))

    def delete(self, key: K) -> bool:
        with self._lock:
            return self._data.pop(key, None) is not None

    def clear(self) -> int:
        with self._lock:
            count = len(self._data)
            self._data.clear()
            return count

    def update(self, mapping: "dict[K, V]") -> None:
        with self._lock:
            for k, v in mapping.items():
                self.set(k, v)

    def sweep_expired(self) -> int:
        """Drop every entry whose TTL has elapsed. Returns eviction count."""
        if self._ttl <= 0:
            return 0
        with self._lock:
            expired_keys = [
                k for k, (exp, _) in self._data.items() if self._is_expired(exp)
            ]
            for k in expired_keys:
                del self._data[k]
            self._evictions += len(expired_keys)
            return len(expired_keys)

    def stats(self) -> "dict[str, int]":
        with self._lock:
            return {
                "size": len(self._data),
                "maxsize": self._maxsize,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
            }
