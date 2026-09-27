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


def test_chinese_query_does_not_fall_back_to_recency():
    graph = TopologyGraph()
    graph.observe(node_id="build", content="建置指令使用套件工具", tags=["scope:alpha"])
    graph.observe(node_id="noise", content="今天午餐安排", tags=["scope:alpha"])
    hits = LocalCandidateRetriever(graph).retrieve("建置指令")
    assert [hit.node_id for hit in hits] == ["build"]
    assert LocalCandidateRetriever(graph).retrieve("無關問題") == []


def test_unicode_tokens_preserve_accents_and_mixed_cjk():
    assert "café" in tokenize("CAFÉ")
    assert "建置" in tokenize("Alpha建置指令")
    assert "alpha" in tokenize("Alpha建置指令")
    assert "unmatched_query" in tokenize("unmatched_query")
    assert "字" in tokenize("字")


def test_nonempty_unsearchable_query_never_uses_recency():
    graph = TopologyGraph()
    graph.observe(node_id="unrelated", content="deployment", tags=[])
    retriever = LocalCandidateRetriever(graph)
    for query in ("a", "🙂", "???"):
        assert retriever.retrieve(query) == []
    assert retriever.retrieve("")  # explicit legacy recency view
