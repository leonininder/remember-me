"""QuarantineQueue spill-to-disk; no drop."""

from __future__ import annotations

from pathlib import Path

import pytest

from remember_me.tfl.quarantine import QuarantineBlockedError, QuarantineQueue


def test_memory_then_spill(tmp_path: Path):
    q = QuarantineQueue(bound_n=2, spill_dir=tmp_path / "spill")
    a = q.enqueue({"entity": "user"}, reason="schema")
    b = q.enqueue({"entity": "user"}, reason="timeout")
    assert q.total_count() == 2
    c = q.enqueue({"entity": "user"}, reason="overflow")
    assert q.spill_count() == 1
    assert q.total_count() == 3
    assert (tmp_path / "spill" / f"{c.id}.json").is_file()
    assert a.id and b.id


def test_no_drop_blocks_without_spill():
    q = QuarantineQueue(bound_n=1, spill_dir=None)
    q.enqueue({"x": 1}, reason="a")
    with pytest.raises(QuarantineBlockedError):
        q.enqueue({"x": 2}, reason="b")
    assert q.blocked
    assert q.total_count() == 1  # nothing dropped


def test_spill_exhausted_blocks(tmp_path: Path):
    q = QuarantineQueue(bound_n=1, spill_dir=tmp_path / "spill", max_spill_items=1)
    q.enqueue({"x": 1}, reason="mem")
    q.enqueue({"x": 2}, reason="spill1")
    with pytest.raises(QuarantineBlockedError, match="exhausted"):
        q.enqueue({"x": 3}, reason="spill2")
    assert q.total_count() == 2  # no drop of third — rejected before accept


def test_drain_memory(tmp_path: Path):
    q = QuarantineQueue(bound_n=5, spill_dir=tmp_path / "spill")
    q.enqueue({"a": 1}, reason="r")
    q.enqueue({"a": 2}, reason="r")
    drained = q.drain_memory(limit=1)
    assert len(drained) == 1
    assert len(q.peek_memory()) == 1
