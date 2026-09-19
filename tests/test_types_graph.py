"""Unit tests: schema, TTL, horizons, graph ops."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from remember_me.graph import TopologyGraph
from remember_me.types import Edge, Horizon, Marker, NodeKind


def test_marker_requires_node_id():
    with pytest.raises(ValidationError):
        Marker(node_id="  ", content_ref="x")


def test_upsert_and_get():
    g = TopologyGraph()
    m = g.observe(node_id="a", content="hello", tags=["t"], salience=0.7)
    assert g.get("a") is not None
    assert m.horizon == Horizon.WORKING
    assert m.ttl_expires_at is not None
    assert len(g) == 1


def test_ttl_purge_working():
    g = TopologyGraph()
    m = Marker(
        node_id="old",
        content_ref="local://old",
        content="x",
        horizon=Horizon.WORKING,
        ttl_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    g.upsert(m, apply_default_ttl=False)
    assert g.get("old") is not None
    purged = g.purge_expired()
    assert purged == 1
    assert g.get("old") is None


def test_durable_ttl_invalidates_not_erases():
    g = TopologyGraph()
    m = Marker(
        node_id="dur",
        content_ref="local://dur",
        content="keep",
        horizon=Horizon.DURABLE,
        ttl_expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    g.upsert(m, apply_default_ttl=False)
    g.purge_expired()
    still = g.get("dur")
    assert still is not None
    assert still.invalid_at is not None
    assert g.all_markers() == []  # filtered as invalid


def test_edges_and_degree():
    g = TopologyGraph()
    g.observe(node_id="a", content="a")
    g.observe(node_id="b", content="b")
    g.add_edge(Edge(source_id="a", target_id="b", relation="related"))
    assert g.get("a").degree == 1
    assert g.get("b").degree == 1


def test_edge_requires_endpoints():
    g = TopologyGraph()
    with pytest.raises(KeyError):
        g.add_edge(Edge(source_id="missing", target_id="also"))


def test_promote_and_by_filters():
    g = TopologyGraph()
    g.observe(node_id="p", content="x", tags=["ui"], kind=NodeKind.FACT)
    g.promote("p", Horizon.DURABLE)
    assert g.get("p").horizon == Horizon.DURABLE
    assert g.by_horizon(Horizon.DURABLE)[0].node_id == "p"
    assert g.by_kind(NodeKind.FACT)[0].node_id == "p"
    assert g.by_tag("ui")[0].node_id == "p"


def test_touch_and_delete():
    g = TopologyGraph()
    g.observe(node_id="t", content="x")
    before = g.get("t").last_touch
    g.touch("t")
    assert g.get("t").last_touch >= before
    assert g.delete("t") is True
    assert g.delete("t") is False


def test_sqlite_roundtrip(tmp_path: Path):
    g = TopologyGraph()
    g.observe(node_id="s1", content="sqlite body", tags=["db"])
    g.observe(node_id="s2", content="other")
    g.add_edge(Edge(source_id="s1", target_id="s2"))
    path = tmp_path / "g.sqlite"
    g.save_sqlite(path)
    g2 = TopologyGraph.load_sqlite(path)
    assert len(g2) == 2
    assert g2.get("s1").content == "sqlite body"
    assert len(g2.edges()) == 1
