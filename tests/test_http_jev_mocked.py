"""HttpJev paths with mocked httpx — System One answers shape, no real network."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from remember_me.jev_client import HttpJev
from remember_me.redact import redact_state
from remember_me.types import JEV_MODEL_PIN, Candidate, NodeKind


def _cands():
    return [
        Candidate(
            node_id="a",
            kind=NodeKind.FACT,
            tags=["t"],
            degree=0,
            last_touch=datetime.now(UTC),
            local_score=0.8,
            tokens_est=8,
            content="secret-body",
        )
    ]


def _system_one_hydrate_answers_batched(node_ids=("a",)):
    """Batched answers keyed ``{node_id}__{qid}``."""
    answers = {}
    for nid in node_ids:
        answers[f"{nid}__hydrate_action"] = {
            "type": "choice",
            "choice": "hydrate_full",
            "confidence": 0.91,
            "probabilities": {
                "hydrate_full": 0.91,
                "stub_only": 0.05,
                "skip": 0.02,
                "promote_durable": 0.01,
                "other": 0.01,
            },
        }
        answers[f"{nid}__need_for_next_turn"] = {
            "type": "score",
            "score": 4,
            "confidence": 0.9,
        }
        answers[f"{nid}__still_matters_for_latest_ask"] = {
            "type": "noul",
            "noul": 0.88,
        }
    return {
        "model": JEV_MODEL_PIN,
        "answers": answers,
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }


def _system_one_hydrate_answers_legacy():
    """Per-candidate (unprefixed) answers for batch_candidates=False."""
    return {
        "model": JEV_MODEL_PIN,
        "answers": {
            "hydrate_action": {
                "type": "choice",
                "choice": "hydrate_full",
                "confidence": 0.91,
                "probabilities": {
                    "hydrate_full": 0.91,
                    "stub_only": 0.05,
                    "skip": 0.02,
                    "promote_durable": 0.01,
                    "other": 0.01,
                },
            },
            "need_for_next_turn": {
                "type": "score",
                "score": 4,
                "confidence": 0.9,
            },
            "still_matters_for_latest_ask": {
                "type": "noul",
                "noul": 0.88,
            },
        },
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }


def _mock_client(resp: MagicMock) -> MagicMock:
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = resp
    return mock_client


def test_http_jev_success_parse_system_one():
    client = HttpJev(api_key="test-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _system_one_hydrate_answers_batched()
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    assert not out[0].failed
    assert out[0].results["hydrate_action"].value == "hydrate_full"
    assert out[0].results["hydrate_action"].confidence == 0.91
    assert out[0].results["need_for_next_turn"].value == 4
    # Noul → bool(noul>=0.5), confidence=noul
    assert out[0].results["still_matters_for_latest_ask"].value is True
    assert out[0].results["still_matters_for_latest_ask"].confidence == 0.88
    assert "content" not in client.last_outbound[0]
    assert client.last_usage == {"input_tokens": 12, "output_tokens": 3}
    assert client.last_response_model == JEV_MODEL_PIN

    # POST URL + batched payload contract
    assert mock_client.post.call_count == 1
    url = mock_client.post.call_args.args[0]
    assert url.endswith("/v1/systemone")
    payload = mock_client.post.call_args.kwargs["json"]
    assert "state" in payload and "questions" in payload
    assert "query" not in payload
    assert "candidates" not in payload  # top-level forbidden
    assert "query_hash" in payload["state"]
    assert payload["state"]["query_hash"] == hashlib.sha256(b"q").hexdigest()
    assert "query_preview" not in payload["state"]
    assert "candidates" in payload["state"]
    assert len(payload["state"]["candidates"]) == 1
    qs = payload["questions"]
    assert qs["a__hydrate_action"]["type"] == "choice"
    assert isinstance(qs["a__hydrate_action"]["criteria"], dict)
    assert "hydrate_full" in qs["a__hydrate_action"]["criteria"]
    assert qs["a__need_for_next_turn"]["type"] == "score"
    assert isinstance(qs["a__need_for_next_turn"]["criteria"], list)
    assert all(isinstance(x, str) for x in qs["a__need_for_next_turn"]["criteria"])
    assert 2 <= len(qs["a__need_for_next_turn"]["criteria"]) <= 10
    assert qs["a__still_matters_for_latest_ask"]["type"] == "noul"
    assert payload["model"] == JEV_MODEL_PIN


def test_http_jev_stores_probabilities_in_raw():
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _system_one_hydrate_answers_batched()
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    raw = out[0].results["hydrate_action"].raw
    assert raw.get("probabilities", {}).get("hydrate_full") == 0.91
    assert raw.get("type") == "choice"


def test_http_jev_include_raw_query_opt_in():
    client = HttpJev(api_key="k", include_raw_query=True)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _system_one_hydrate_answers_batched()
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        client.decide_hydrate("raw-query-text", redact_state(_cands()))
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["state"]["query_preview"] == "raw-query-text"
    assert "query_hash" in payload["state"]


def test_http_jev_default_base_url_systemone():
    client = HttpJev(api_key="k")
    assert client.base_url.endswith("/v1/systemone")
    assert "/v1/jev" not in client.base_url


def test_http_jev_403_denied():
    client = HttpJev(api_key="bad")
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    assert out[0].denied


def test_http_jev_timeout_exception():
    client = HttpJev(api_key="k")
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.side_effect = TimeoutError("slow")
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    assert out[0].timed_out


def test_http_jev_malformed_json():
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("bad json")
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    assert out[0].malformed


def test_http_jev_admit_success():
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": JEV_MODEL_PIN,
        "answers": {
            "admit": {"type": "choice", "choice": "admit", "confidence": 0.8},
            "node_kind": {"type": "choice", "choice": "fact", "confidence": 0.8},
        },
    }
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_admit({"node_id": "n", "kind": "fact", "tags": [], "salience": 0.5})
    assert not out.failed
    assert out.results["admit"].value == "admit"
    url = mock_client.post.call_args.args[0]
    assert url.endswith("/v1/systemone")
    payload = mock_client.post.call_args.kwargs["json"]
    assert "state" in payload and "questions" in payload
    assert payload["state"]["node_id"] == "n"
    assert "query" not in payload
    assert payload["questions"]["admit"]["type"] == "choice"
    assert isinstance(payload["questions"]["admit"]["criteria"], dict)
    assert "admit" in payload["questions"]["admit"]["criteria"]
    assert payload["questions"]["node_kind"]["type"] == "choice"
    assert isinstance(payload["questions"]["node_kind"]["criteria"], dict)


def test_http_jev_500_malformed():
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    assert out[0].malformed


def test_http_jev_missing_answers_key():
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}  # no answers (old decisions shape must fail)
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    assert out[0].malformed
    assert out[0].error == "missing_answers"


def test_http_jev_rejects_legacy_decisions_shape():
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "decisions": [
            {
                "node_id": "a",
                "results": {
                    "hydrate_action": {"value": "hydrate_full", "confidence": 0.91},
                },
            }
        ]
    }
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    assert out[0].malformed


def test_http_jev_batched_multi_candidate_one_post():
    cands = [
        Candidate(
            node_id="a",
            kind=NodeKind.FACT,
            tags=["t"],
            degree=0,
            last_touch=datetime.now(UTC),
            local_score=0.8,
            tokens_est=8,
            content="x",
        ),
        Candidate(
            node_id="b",
            kind=NodeKind.FACT,
            tags=["t"],
            degree=0,
            last_touch=datetime.now(UTC),
            local_score=0.5,
            tokens_est=4,
            content="y",
        ),
    ]
    client = HttpJev(api_key="k", batch_candidates=True)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _system_one_hydrate_answers_batched(("a", "b"))
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(cands))
    assert len(out) == 2
    assert mock_client.post.call_count == 1
    assert not out[0].failed and not out[1].failed
    assert out[0].node_id == "a" and out[1].node_id == "b"
    payload = mock_client.post.call_args.kwargs["json"]
    assert len(payload["state"]["candidates"]) == 2
    assert "a__hydrate_action" in payload["questions"]
    assert "b__hydrate_action" in payload["questions"]


def test_http_jev_batch_partial_missing_node_malformed():
    """One node missing answers → that node malformed; others OK."""
    cands = [
        Candidate(
            node_id="a",
            kind=NodeKind.FACT,
            tags=["t"],
            degree=0,
            last_touch=datetime.now(UTC),
            local_score=0.8,
            tokens_est=8,
            content="x",
        ),
        Candidate(
            node_id="b",
            kind=NodeKind.FACT,
            tags=["t"],
            degree=0,
            last_touch=datetime.now(UTC),
            local_score=0.5,
            tokens_est=4,
            content="y",
        ),
    ]
    # Only node a answers present
    body = _system_one_hydrate_answers_batched(("a",))
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = body
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(cands))
    assert not out[0].failed
    assert out[1].malformed
    assert out[1].error == "missing_node_answers"


def test_http_jev_batch_whole_fail_all_nodes():
    cands = [
        Candidate(
            node_id="a",
            kind=NodeKind.FACT,
            tags=["t"],
            degree=0,
            last_touch=datetime.now(UTC),
            local_score=0.8,
            tokens_est=8,
            content="x",
        ),
        Candidate(
            node_id="b",
            kind=NodeKind.FACT,
            tags=["t"],
            degree=0,
            last_touch=datetime.now(UTC),
            local_score=0.5,
            tokens_est=4,
            content="y",
        ),
    ]
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(cands))
    assert len(out) == 2
    assert all(r.denied for r in out)
    assert mock_client.post.call_count == 1


def test_http_jev_empty_candidates():
    client = HttpJev(api_key="k")
    mock_client = _mock_client(MagicMock())
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", [])
    assert out == []
    assert mock_client.post.call_count == 0


def test_http_jev_batch_candidates_false_per_node():
    """Debug fallback: one POST per candidate with unprefixed questions."""
    cands = [
        Candidate(
            node_id="a",
            kind=NodeKind.FACT,
            tags=["t"],
            degree=0,
            last_touch=datetime.now(UTC),
            local_score=0.8,
            tokens_est=8,
            content="x",
        ),
        Candidate(
            node_id="b",
            kind=NodeKind.FACT,
            tags=["t"],
            degree=0,
            last_touch=datetime.now(UTC),
            local_score=0.5,
            tokens_est=4,
            content="y",
        ),
    ]
    client = HttpJev(api_key="k", batch_candidates=False)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _system_one_hydrate_answers_legacy()
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(cands))
    assert len(out) == 2
    assert mock_client.post.call_count == 2
    payload = mock_client.post.call_args_list[0].kwargs["json"]
    assert "candidate" in payload["state"]
    assert "hydrate_action" in payload["questions"]


def test_http_jev_decide_emit_payload_shape_mocked():
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": JEV_MODEL_PIN,
        "answers": {
            "emit_action": {
                "type": "choice",
                "choice": "allow_emit",
                "confidence": 0.92,
            },
            "leak_risk": {"type": "noul", "noul": 0.1},
            "on_topic": {"type": "noul", "noul": 0.9},
        },
    }
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_emit(
            sink="audit_log",
            payload_meta={"proposed_summary": "hi", "node_id": "e1"},
        )
    assert not out.failed
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["state"]["sink"] == "audit_log"
    assert "emit_action" in payload["questions"]
    assert isinstance(payload["questions"]["emit_action"]["criteria"], dict)
    assert "content" not in payload["state"]


def test_http_jev_decide_writeback_payload_shape_mocked():
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": JEV_MODEL_PIN,
        "answers": {
            "writeback_action": {
                "type": "choice",
                "choice": "allow_writeback",
                "confidence": 0.9,
            },
            "writeback_need": {"type": "score", "score": 4, "confidence": 0.88},
            "writeback_still_safe": {"type": "noul", "noul": 0.85},
        },
    }
    mock_client = _mock_client(mock_resp)
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_writeback(
            target="wiki_stage",
            proposed={"node_id": "n1", "kind": "fact", "tags": ["t"], "salience": 0.5},
        )
    assert not out.failed
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["state"]["target"] == "wiki_stage"
    assert "writeback_action" in payload["questions"]
    assert isinstance(payload["questions"]["writeback_action"]["criteria"], dict)
    assert isinstance(payload["questions"]["writeback_need"]["criteria"], list)
    assert all(isinstance(x, str) for x in payload["questions"]["writeback_need"]["criteria"])
    assert "body" not in payload["state"]
