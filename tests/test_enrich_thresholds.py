"""Enrichment + policy thresholds: structured egress only; bands unchanged."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from remember_me.enrich import (
    FIT_CLASSES,
    INTENT_CLASSES,
    INTENT_FOCUSES,
    LENGTH_BUCKETS,
    TOPIC_FAMILIES,
    classify_intent,
    classify_intent_focus,
    enrich_candidate_dict,
    enrich_candidate_dicts,
    intent_topic_fit,
    length_bucket,
    overlap_tag_count,
    query_enrichment,
    stub_tags,
    topic_family,
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
    # "UI language" must classify as locale, not ui (v1 bug).
    assert classify_intent("What UI language do I prefer?") == "preference_locale"
    assert classify_intent("health insurance details") == "sensitive_avoid"
    assert classify_intent("Locale preference without health notes") == "preference_locale"
    assert classify_intent("Beverage preferences today?") == "preference_food"
    assert classify_intent("What testing approach before merge?") == "preference_workflow"
    assert classify_intent("zzz unknown") == "other"
    assert all(classify_intent(q) in INTENT_CLASSES for q in ["theme", "x" * 200])
    assert length_bucket("hi") == "short"
    assert length_bucket("x" * 50) == "medium"
    assert length_bucket("x" * 200) == "long"
    assert length_bucket("x" * 50) in LENGTH_BUCKETS


def test_intent_focus_finer_than_class():
    assert classify_intent_focus("What is my editor theme preference?") == "theme"
    assert classify_intent_focus("Which monospace font do I prefer?") == "font"
    assert classify_intent_focus("What UI language do I prefer?") == "language"
    assert classify_intent_focus("Afternoon drink preference?") == "drink"
    assert classify_intent_focus("zzz") == "other"
    assert classify_intent_focus("theme") in INTENT_FOCUSES


def test_query_enrichment_has_no_raw_query():
    q = "What is my editor theme preference?"
    enr = query_enrichment(q)
    assert set(enr.keys()) == {"intent_class", "intent_focus", "length_bucket"}
    assert q not in enr.values()
    assert "query" not in enr
    assert "query_preview" not in enr


def test_topic_family_and_overlap_ontology():
    assert topic_family(["preference", "ui", "theme"]) == "ui_theme"
    assert topic_family(["preference", "locale", "language"]) == "locale_lang"
    assert topic_family(["noise", "sports"]) == "noise"
    assert topic_family(["overshare", "health"]) == "overshare"
    assert topic_family(["x"]) == "other"
    assert topic_family(["theme"]) in TOPIC_FAMILIES
    assert overlap_tag_count(["preference", "ui", "theme"], "preference_ui") >= 2
    assert overlap_tag_count(["noise"], "preference_ui") == 0
    fit = intent_topic_fit(
        intent_class="preference_ui",
        intent_focus="theme",
        family="ui_theme",
        overlap=3,
    )
    assert fit == "strong_match"
    assert fit in FIT_CLASSES
    assert (
        intent_topic_fit(
            intent_class="preference_ui",
            intent_focus="theme",
            family="noise",
            overlap=0,
        )
        == "mismatch"
    )


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
            "tags": ["preference", "ui", "theme"],
            "degree": 1,
            "last_touch": "2026-09-22T00:00:00Z",
            "local_score": 0.8,
            "tokens_est": 12,
            "content": "LEAK",
            "salience": 0.9,
        },
        intent_class="preference_ui",
        intent_focus="theme",
        rank_in_topk=1,
        salience=0.9,
    )
    assert "content" not in d
    assert d["stub_tags"] == stub_tags(["preference", "ui", "theme"])
    assert d["topic_family"] == "ui_theme"
    assert d["intent_topic_fit"] == "strong_match"
    assert d["candidate_rank_in_topk"] == 1
    assert d["salience_bucket"] == "high"
    assert d["stub_token_bucket"] == "small"
    assert d["overlap_tag_count"] >= 2
    assert set(d.keys()) <= ALLOWED_OUTBOUND_KEYS


def test_enrich_candidate_dicts_assigns_ranks():
    cands = [
        {
            "node_id": "a",
            "kind": "fact",
            "tags": ["theme", "ui"],
            "degree": 1,
            "last_touch": "2026-09-22T00:00:00Z",
            "local_score": 0.9,
            "tokens_est": 10,
        },
        {
            "node_id": "b",
            "kind": "fact",
            "tags": ["noise"],
            "degree": 0,
            "last_touch": "2026-09-22T00:00:00Z",
            "local_score": 0.2,
            "tokens_est": 8,
        },
    ]
    out = enrich_candidate_dicts(
        cands, intent_class="preference_ui", intent_focus="theme"
    )
    assert out[0]["candidate_rank_in_topk"] == 1
    assert out[1]["candidate_rank_in_topk"] == 2
    assert out[0]["intent_topic_fit"] == "strong_match"
    assert out[1]["intent_topic_fit"] == "mismatch"


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
            salience=0.9,
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
    assert state["intent_focus"] == "theme"
    assert state["length_bucket"] == "short"
    assert "query_preview" not in state
    assert "query" not in state
    assert q not in str(state)
    cand0 = state["candidates"][0]
    assert "stub_tags" in cand0
    assert "theme" in cand0["stub_tags"]
    assert cand0["topic_family"] == "ui_theme"
    assert cand0["intent_topic_fit"] == "strong_match"
    assert cand0["candidate_rank_in_topk"] == 1
    assert cand0["salience_bucket"] == "high"
    assert "content" not in cand0
    qs = payload["questions"]
    hyd = qs["pref_theme__hydrate_action"]
    assert "intent_focus" in hyd["instructions"]
    assert "intent_topic_fit" in str(hyd["criteria"])
