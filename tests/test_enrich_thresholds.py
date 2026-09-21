"""Enrichment + policy thresholds: structured egress only; bands unchanged."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from remember_me.enrich import (
    INTENT_CLASSES,
    LENGTH_BUCKETS,
    classify_intent,
    enrich_candidate_dict,
    length_bucket,
    query_enrichment,
    stub_tags,
)
from remember_me.jev_client import JEV_MODEL_PIN, HttpJev
from remember_me.policy import T_ACCEPT, T_ESCALATE, map_hydrate_action
from remember_me.redact import ALLOWED_OUTBOUND_KEYS
from remember_me.types import (
    Q_HYDRATE_ACTION,
    Q_STILL_MATTERS,
    Candidate,
    HydrateAction,
    JevBatchResponse,
    JevQuestionResult,
    NodeKind,
)


def test_thresholds_unchanged_after_enrichment_path():
    """David/JustinSun: do NOT lower bands into conf≈0.2–0.5 noise."""
    assert T_ACCEPT == 0.85
    assert T_ESCALATE == 0.55


def test_low_conf_still_skips_under_held_thresholds():
    """Live-like conf 0.4 remains reject/skip — enrichment must raise conf, not floors."""
    resp = JevBatchResponse(
        node_id="c1",
        results={
            Q_HYDRATE_ACTION: JevQuestionResult(
                question_id=Q_HYDRATE_ACTION, value="stub_only", confidence=0.4
            ),
            Q_STILL_MATTERS: JevQuestionResult(
                question_id=Q_STILL_MATTERS, value=True, confidence=0.5
            ),
        },
    )
    cand = Candidate(
        node_id="c1",
        kind=NodeKind.FACT,
        tags=["preference", "ui"],
        degree=1,
        last_touch=datetime.now(UTC),
        local_score=0.9,
        tokens_est=10,
    )
    d = map_hydrate_action(resp, cand)
    assert d.action == HydrateAction.SKIP
    assert not d.fail_closed


def test_intent_and_length_closed_enums():
    assert classify_intent("What is my editor theme preference?") == "preference_ui"
    assert classify_intent("What language do I prefer?") == "preference_locale"
    assert classify_intent("health insurance details") == "sensitive_avoid"
    assert classify_intent("zzz unknown") == "other"
    assert all(classify_intent(q) in INTENT_CLASSES for q in ["theme", "x" * 200])
    assert length_bucket("hi") == "short"
    assert length_bucket("x" * 50) == "medium"
    assert length_bucket("x" * 200) == "long"
    assert length_bucket("x" * 50) in LENGTH_BUCKETS


def test_query_enrichment_has_no_raw_query():
    q = "What is my editor theme preference?"
    enr = query_enrichment(q)
    assert set(enr.keys()) == {"intent_class", "length_bucket"}
    assert q not in enr.values()
    assert "query" not in enr
    assert "query_preview" not in enr


def test_stub_tags_capped_and_allowlisted():
    tags = ["UI", "preference", "ui", "x" * 100] + [f"t{i}" for i in range(20)]
    st = stub_tags(tags)
    assert len(st) <= 8
    assert "ui" in st
    assert all(len(t) <= 32 for t in st)
    d = enrich_candidate_dict(
        {
            "node_id": "n1",
            "kind": "fact",
            "tags": ["preference", "ui"],
            "degree": 1,
            "last_touch": "2026-09-22T00:00:00Z",
            "local_score": 0.8,
            "tokens_est": 12,
            "content": "LEAK",
        }
    )
    assert "content" not in d
    assert d["stub_tags"] == stub_tags(["preference", "ui"])
    assert set(d.keys()) <= ALLOWED_OUTBOUND_KEYS


def test_http_jev_state_includes_enrichment_not_raw_query():
    client = HttpJev(api_key="k", include_raw_query=False)
    cands = [
        Candidate(
            node_id="pref_theme",
            kind=NodeKind.FACT,
            tags=["preference", "ui", "theme"],
            degree=1,
            last_touch=datetime.now(UTC),
            local_score=0.85,
            tokens_est=24,
            content="dark mode SECRET",
        )
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": JEV_MODEL_PIN,
        "answers": {
            "pref_theme__hydrate_action": {
                "type": "choice",
                "choice": "stub_only",
                "confidence": 0.9,
            },
            "pref_theme__need_for_next_turn": {
                "type": "score",
                "score": 3,
                "confidence": 0.8,
            },
            "pref_theme__still_matters_for_latest_ask": {
                "type": "noul",
                "noul": 0.7,
            },
        },
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_resp
    q = "What is my editor theme preference?"
    with patch("httpx.Client", return_value=mock_client):
        client.decide_hydrate(q, cands)
    payload = mock_client.post.call_args.kwargs["json"]
    state = payload["state"]
    assert state["query_hash"] == hashlib.sha256(q.encode()).hexdigest()
    assert state["intent_class"] == "preference_ui"
    assert state["length_bucket"] == "short"
    assert "query_preview" not in state
    assert "query" not in state
    assert q not in str(state)
    cand0 = state["candidates"][0]
    assert "stub_tags" in cand0
    assert "theme" in cand0["stub_tags"]
    assert "content" not in cand0
    qs = payload["questions"]
    hyd = qs["pref_theme__hydrate_action"]
    assert "intent_class" in hyd["instructions"]
    assert "stub_tags" in str(hyd["criteria"])
