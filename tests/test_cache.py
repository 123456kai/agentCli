import json
from pathlib import Path
import tempfile

from agentcli.analysis.cache import NarrativeCache


def test_cache_set_and_get():
    cache_dir = Path(tempfile.mkdtemp())
    cache = NarrativeCache(cache_dir)

    cache.set("src/a.py:abc123:10-20", {"summary": "does X", "design_notes": "because Y", "warnings": None})

    entry = cache.get("src/a.py:abc123:10-20")
    assert entry is not None
    assert entry["summary"] == "does X"
    assert entry["design_notes"] == "because Y"
    assert entry["warnings"] is None


def test_cache_miss_returns_none():
    cache_dir = Path(tempfile.mkdtemp())
    cache = NarrativeCache(cache_dir)

    assert cache.get("nonexistent:hash:1-5") is None


def test_cache_overwrite():
    cache_dir = Path(tempfile.mkdtemp())
    cache = NarrativeCache(cache_dir)

    cache.set("key:hash:1-5", {"summary": "old"})
    cache.set("key:hash:1-5", {"summary": "new"})

    assert cache.get("key:hash:1-5")["summary"] == "new"


def test_cache_file_hash_changes_invalidates():
    cache_dir = Path(tempfile.mkdtemp())
    cache = NarrativeCache(cache_dir)

    cache.set("src/a.py:oldhash:10-20", {"summary": "stale"})
    # Different hash for same file location should miss
    assert cache.get("src/a.py:newhash:10-20") is None


def test_make_cache_key():
    from agentcli.analysis.cache import make_cache_key

    key = make_cache_key("src/a.py", "abc123def", 42, 68)
    assert key == "src/a.py:abc123def:42-68"
