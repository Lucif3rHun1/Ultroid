"""Tests for pyUltroid._misc.ttl_cache.TTLCache."""
import threading
import time

import pytest

from pyUltroid._misc.ttl_cache import TTLCache


def test_set_get_basic():
    c = TTLCache(maxsize=10, ttl=0)
    c.set("a", 1)
    c.set("b", 2)
    assert c.get("a") == 1
    assert c.get("b") == 2
    assert c.get("missing") is None
    assert c.get("missing", "default") == "default"


def test_dict_protocol():
    c = TTLCache()
    c["x"] = 42
    assert c["x"] == 42
    assert "x" in c
    assert "missing" not in c
    with pytest.raises(KeyError):
        _ = c["missing"]
    del c["x"]
    assert "x" not in c


def test_lru_eviction():
    c = TTLCache(maxsize=2, ttl=0)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)  # evicts "a"
    assert "a" not in c
    assert "b" in c
    assert "c" in c
    assert len(c) == 2


def test_lru_order_on_get():
    c = TTLCache(maxsize=2, ttl=0)
    c.set("a", 1)
    c.set("b", 2)
    _ = c.get("a")  # touch "a", making "b" LRU
    c.set("c", 3)  # should evict "b"
    assert "a" in c
    assert "b" not in c
    assert "c" in c


def test_ttl_expiry():
    c = TTLCache(maxsize=10, ttl=0.1)
    c.set("a", 1)
    assert c.get("a") == 1
    time.sleep(0.15)
    assert c.get("a") is None


def test_per_entry_ttl():
    c = TTLCache(ttl=0)
    c.set("a", 1, ttl=0.1)
    c.set("b", 2)  # no expiry
    time.sleep(0.15)
    assert c.get("a") is None
    assert c.get("b") == 2


def test_ttl_disabled():
    c = TTLCache(ttl=0)
    c.set("a", 1)
    time.sleep(0.05)
    assert c.get("a") == 1


def test_sweep_expired():
    c = TTLCache(maxsize=10, ttl=0.1)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3, ttl=10)  # long-lived
    time.sleep(0.15)
    evicted = c.sweep_expired()
    assert evicted == 2
    assert "c" in c
    assert "a" not in c


def test_clear():
    c = TTLCache()
    for i in range(5):
        c.set(f"k{i}", i)
    assert len(c) == 5
    removed = c.clear()
    assert removed == 5
    assert len(c) == 0


def test_stats():
    c = TTLCache()
    c.set("a", 1)
    _ = c.get("a")   # hit
    _ = c.get("a")   # hit
    _ = c.get("b")   # miss
    s = c.stats()
    assert s["hits"] == 2
    assert s["misses"] == 1
    assert s["size"] == 1
    assert s["maxsize"] == 1024  # default


def test_update():
    c = TTLCache()
    c.update({"a": 1, "b": 2, "c": 3})
    assert c.get("a") == 1
    assert c.get("b") == 2
    assert c.get("c") == 3


def test_delete():
    c = TTLCache()
    c.set("a", 1)
    assert c.delete("a") is True
    assert c.delete("a") is False  # second time
    assert "a" not in c


def test_iter():
    c = TTLCache()
    c.update({"a": 1, "b": 2, "c": 3})
    assert set(c) == {"a", "b", "c"}


def test_thread_safety():
    """20 threads hammering set/get — must not raise."""
    c = TTLCache(maxsize=500, ttl=10)
    errors = []

    def worker(prefix):
        try:
            for i in range(100):
                c.set(f"{prefix}{i}", i)
                _ = c.get(f"{prefix}{i}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(f"t{i}_",)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(c) <= 500


def test_invalid_maxsize():
    with pytest.raises(ValueError):
        TTLCache(maxsize=-1)


def test_invalid_ttl():
    with pytest.raises(ValueError):
        TTLCache(ttl=-1)
