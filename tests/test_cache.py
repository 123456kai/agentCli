import json
from pathlib import Path
import tempfile

from agentcli.analysis.cache import NarrativeCache, make_cache_key


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
    key = make_cache_key("src/a.py", "abc123def", 42, 68)
    assert key == "src/a.py:abc123def:42-68"


def test_cache_persistence():
    """Data survives across different NarrativeCache instances pointing to the same directory."""
    cache_dir = Path(tempfile.mkdtemp())
    cache1 = NarrativeCache(cache_dir)
    cache1.set("src/a.py:abc123:10-20", {"summary": "persistent", "design_notes": "survives", "warnings": None})

    cache2 = NarrativeCache(cache_dir)
    entry = cache2.get("src/a.py:abc123:10-20")
    assert entry is not None
    assert entry["summary"] == "persistent"
    assert entry["design_notes"] == "survives"
    assert entry["warnings"] is None


def test_get_by_prefix():
    """get_by_prefix returns only entries matching the given file_path and content_hash."""
    cache_dir = Path(tempfile.mkdtemp())
    cache = NarrativeCache(cache_dir)

    cache.set("src/a.py:hash1:10-20", {"summary": "first block"})
    cache.set("src/a.py:hash1:30-40", {"summary": "second block"})
    cache.set("src/b.py:hash2:5-15", {"summary": "other file"})

    results = cache.get_by_prefix("src/a.py", "hash1")
    assert len(results) == 2
    keys = [k for k, v in results]
    assert "src/a.py:hash1:10-20" in keys
    assert "src/a.py:hash1:30-40" in keys

    results_other = cache.get_by_prefix("src/b.py", "hash2")
    assert len(results_other) == 1
    assert results_other[0][0] == "src/b.py:hash2:5-15"


def test_corrupted_json_recovery():
    """Corrupted narratives.json should not crash; cache starts empty."""
    cache_dir = Path(tempfile.mkdtemp())
    store_path = cache_dir / "narratives.json"
    store_path.write_text("this is not valid json", encoding="utf-8")

    cache = NarrativeCache(cache_dir)
    assert cache.get("any:key:1-5") is None
