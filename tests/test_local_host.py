"""Host contract: scope isolation, budgets, honest audit, and invalid input."""
import hashlib
import json

import pytest

from remember_me import FakeJev, MemoryPipeline, TopologyGraph
from remember_me.local_host import assemble_context, load_graph


def test_scope_private_review_and_budget():
    graph = TopologyGraph()
    for node_id, tags in [
        ("approved", ["scope:alpha"]), ("other", ["scope:beta"]),
        ("reviewed", ["scope:alpha", "review"]),
        ("private", ["scope:alpha", "private"]),
        ("ambiguous", ["scope:alpha", "scope:beta"]),
    ]:
        graph.observe(node_id=node_id, content="build 漢字", tags=tags)
    output = assemble_context(graph, "build", scope="alpha")
    assert output["audit"]["included_ids"] == ["approved"]
    assert output["audit"]["review_ids"] == ["reviewed"]
    assert "build 漢字" not in json.dumps(output["audit"], ensure_ascii=False)
    for budget in (0, 1, 30):
        limited = assemble_context(graph, "build", scope="alpha", max_bytes=budget)
        assert limited["audit"]["context_bytes"] <= budget
        assert not limited["audit"]["included_ids"]
    exact = output["audit"]["context_bytes"]
    assert assemble_context(graph, "build", scope="alpha", max_bytes=exact)["audit"][
        "included_ids"] == ["approved"]
    assert not assemble_context(graph, "build", scope="alpha", max_bytes=exact - 1)[
        "audit"]["included_ids"]


def test_empty_scope_and_invalid_limits():
    for kwargs in ({"scope": ""}, {"scope": "alpha", "top_k": 0},
                   {"scope": "alpha", "max_bytes": -1}):
        with pytest.raises(ValueError):
            assemble_context(TopologyGraph(), "q", **kwargs)


def test_load_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text(json.dumps([{"id": "x", "text": "a", "tags": []}] * 2), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_graph(path)


def test_dual_context_has_hash_not_query_prefix():
    query = "sensitive user query retained nowhere in context"
    result = MemoryPipeline(client=FakeJev()).run_dual(query, egress_summary="summary")
    assert result.egress.context["query_sha256"] == hashlib.sha256(query.encode()).hexdigest()
    assert query[:32] not in json.dumps(result.egress.context)


@pytest.mark.parametrize("action", ["unknown_action", "other", None, {}, True])
def test_unknown_action_cannot_hydrate(action):
    from datetime import UTC, datetime

    from remember_me.policy import map_hydrate_action
    from remember_me.types import Q_HYDRATE_ACTION, Candidate, JevBatchResponse, JevQuestionResult

    candidate = Candidate(node_id="x", kind="fact", last_touch=datetime.now(UTC), local_score=1)
    response = JevBatchResponse(node_id="x", results={Q_HYDRATE_ACTION: JevQuestionResult(
        question_id=Q_HYDRATE_ACTION, value=action, confidence=1.0,
    )})
    decision = map_hydrate_action(response, candidate)
    assert decision.action.value == "skip"
    assert decision.fail_closed

def test_cli_builds_real_messages_without_test_double():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    run = subprocess.run([
        sys.executable, "-m", "remember_me.local_host", "--memories",
        str(root / "examples/host_memories.json"), "--scope", "alpha", "--query", "build",
    ], capture_output=True, text=True, check=True)
    output = json.loads(run.stdout)
    assert output["audit"]["policy"] == "local-scope-rules-v1"
    assert output["audit"]["included_ids"] == ["alpha_build"]
    assert "python -m build" in output["messages"][1]["content"]
    assert "npm run build" not in output["messages"][1]["content"]
    assert "pending approval" not in output["messages"][1]["content"]


def test_same_task_evaluation_counts():
    import runpy
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "examples/evaluate_local_host.py"
    report = runpy.run_path(str(path))["run"]()
    gated = report["modes"]["local_scope_gate"]
    assert gated["retained"] == 4
    assert gated["missed"] == 0
    assert gated["wrongly_included"] == 0
    assert report["modes"]["local_topk"]["wrongly_included"] > 0
    assert all(case["context_bytes"] <= report["max_bytes"] for case in gated["cases"])


@pytest.mark.parametrize("query", ["", "   ", "a", "🙂", "???"])
def test_host_rejects_unsearchable_input(query):
    graph = TopologyGraph()
    graph.observe(node_id="unrelated", content="deploy staging", tags=["scope:alpha"])
    with pytest.raises(ValueError, match="searchable"):
        assemble_context(graph, query, scope="alpha")


@pytest.mark.parametrize("max_bytes", [float("inf"), float("nan"), 1.5, True])
def test_host_rejects_non_integer_budget(max_bytes):
    with pytest.raises(ValueError):
        assemble_context(TopologyGraph(), "build", scope="alpha", max_bytes=max_bytes)


def test_chinese_host_selects_only_keyword_match():
    graph = TopologyGraph()
    graph.observe(node_id="build", content="建置指令使用套件工具", tags=["scope:alpha"])
    graph.observe(node_id="noise", content="今天午餐安排", tags=["scope:alpha"])
    assert assemble_context(graph, "建置指令", scope="alpha")["audit"]["included_ids"] == ["build"]
    assert assemble_context(graph, "無關問題", scope="alpha")["audit"]["included_ids"] == []
