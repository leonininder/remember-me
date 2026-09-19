"""Local retriever — never uses Jev ranking."""

from __future__ import annotations

from remember_me.graph import TopologyGraph
from remember_me.retrieve import LocalCandidateRetriever, tokenize


def test_tokenize():
    assert "dark" in tokenize("Dark Theme preference")


def test_retrieve_ranks_relevant():
    g = TopologyGraph()
    g.observe(node_id="theme", content="dark theme preference", tags=["ui", "theme"], salience=0.9)
    g.observe(node_id="noise", content="cricket scoreline", tags=["sports"], salience=0.1)
    r = LocalCandidateRetriever(g, top_k=5)
    hits = r.retrieve("editor theme preference")
    assert hits
    assert hits[0].node_id == "theme"
    assert all(h.local_score >= 0 for h in hits)


def test_empty_graph():
    r = LocalCandidateRetriever(TopologyGraph())
    assert r.retrieve("anything") == []
