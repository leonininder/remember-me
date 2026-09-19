"""HttpJev paths with mocked httpx — no real network."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from remember_me.jev_client import HttpJev
from remember_me.redact import redact_state
from remember_me.types import Candidate, NodeKind


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


def test_http_jev_success_parse():
    client = HttpJev(api_key="test-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "decisions": [
            {
                "node_id": "a",
                "results": {
                    "hydrate_action": {"value": "hydrate_full", "confidence": 0.91},
                    "need_for_next_turn": {"value": 4, "confidence": 0.9},
                    "still_matters_for_latest_ask": {"value": True, "confidence": 0.88},
                },
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_resp
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    assert not out[0].failed
    assert out[0].results["hydrate_action"].value == "hydrate_full"
    # Ensure outbound was redacted
    assert "content" not in client.last_outbound[0]


def test_http_jev_403_denied():
    client = HttpJev(api_key="bad")
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_resp
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
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_resp
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    assert out[0].malformed


def test_http_jev_admit_success():
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "decisions": [
            {
                "node_id": "n",
                "results": {
                    "admit": {"value": "admit", "confidence": 0.8},
                    "node_kind": {"value": "fact", "confidence": 0.8},
                },
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_resp
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_admit({"node_id": "n", "kind": "fact", "tags": [], "salience": 0.5})
    assert not out.failed


def test_http_jev_500_malformed():
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_resp
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    assert out[0].malformed


def test_http_jev_missing_decisions_key():
    client = HttpJev(api_key="k")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_resp
    with patch("httpx.Client", return_value=mock_client):
        out = client.decide_hydrate("q", redact_state(_cands()))
    assert out[0].malformed
