"""HttpJevReconcileGate chaos — mock 401/429/timeout → quarantine/escalate.

Never md-append; never silent APPLY on deny/timeout/malformed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from remember_me.tfl.ledger import FactLedger
from remember_me.tfl.policy import ApplyAction
from remember_me.tfl.quarantine import QuarantineQueue
from remember_me.tfl.reconcile import HttpJevReconcileGate, ReconcileEngine
from remember_me.tfl.types import CandidateFact


def _cand() -> CandidateFact:
    return CandidateFact(
        entity="user",
        attribute="weather",
        qualifier="local",
        value_struct={"condition": "rainy"},
        observed_at=datetime(2026, 9, 22, 9, 0, tzinfo=UTC),
        source_event_id="evt_chaos",
        extract_method="deterministic",
        salience_hint="ephemeral",
    )


def _mock_client(resp: MagicMock | None = None, *, side_effect=None) -> MagicMock:
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    if side_effect is not None:
        mock_client.post.side_effect = side_effect
    else:
        mock_client.post.return_value = resp
    return mock_client


def _resp(status: int, *, headers: dict | None = None, json_body=None, json_exc=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.headers = headers or {}
    if json_exc is not None:
        mock_resp.json.side_effect = json_exc
    elif json_body is not None:
        mock_resp.json.return_value = json_body
    else:
        mock_resp.json.return_value = {}
    return mock_resp


def _engine(
    tmp_path: Path, gate: HttpJevReconcileGate
) -> tuple[ReconcileEngine, QuarantineQueue, FactLedger]:
    ledger = FactLedger(tmp_path / "l.sqlite")
    q = QuarantineQueue(bound_n=16, spill_dir=tmp_path / "spill")
    eng = ReconcileEngine(ledger, gate, quarantine=q)
    return eng, q, ledger


@pytest.mark.parametrize("code", [401, 403])
def test_http_reconcile_auth_denied_quarantines(tmp_path: Path, code: int):
    gate = HttpJevReconcileGate(api_key="bad")
    eng, q, ledger = _engine(tmp_path, gate)
    with patch("httpx.Client", return_value=_mock_client(_resp(code))):
        result = eng.reconcile_candidate(_cand())
    assert result.action == ApplyAction.QUARANTINE
    assert result.fail_closed
    assert not result.applied
    assert q.total_count() == 1
    assert ledger.count_active() == 0
    assert f"http_{code}" in (result.reason or "")


def test_http_reconcile_429_timed_out_quarantines(tmp_path: Path):
    gate = HttpJevReconcileGate(api_key="k")
    eng, q, ledger = _engine(tmp_path, gate)
    with patch(
        "httpx.Client",
        return_value=_mock_client(_resp(429, headers={"Retry-After": "7"})),
    ):
        result = eng.reconcile_candidate(_cand())
    assert result.action == ApplyAction.QUARANTINE
    assert "http_429" in (result.reason or "")
    assert "retry_after=7" in (result.reason or "")
    assert q.total_count() == 1
    assert ledger.count_active() == 0


def test_http_reconcile_timeout_exception(tmp_path: Path):
    gate = HttpJevReconcileGate(api_key="k")
    eng, q, _ = _engine(tmp_path, gate)
    with patch(
        "httpx.Client",
        return_value=_mock_client(side_effect=httpx.TimeoutException("slow")),
    ):
        result = eng.reconcile_candidate(_cand())
    assert result.action == ApplyAction.QUARANTINE
    assert result.fail_closed
    assert q.total_count() == 1


def test_http_reconcile_malformed_json(tmp_path: Path):
    gate = HttpJevReconcileGate(api_key="k")
    eng, q, _ = _engine(tmp_path, gate)
    with patch(
        "httpx.Client",
        return_value=_mock_client(_resp(200, json_exc=ValueError("nope"))),
    ):
        result = eng.reconcile_candidate(_cand())
    assert result.action == ApplyAction.QUARANTINE
    assert "invalid_json" in (result.reason or "")


def test_http_reconcile_missing_answers_malformed(tmp_path: Path):
    gate = HttpJevReconcileGate(api_key="k")
    eng, q, _ = _engine(tmp_path, gate)
    with patch(
        "httpx.Client",
        return_value=_mock_client(_resp(200, json_body={"model": "jev-1.13.0"})),
    ):
        result = eng.reconcile_candidate(_cand())
    assert result.action == ApplyAction.QUARANTINE
    assert "missing_answers" in (result.reason or "")


def test_http_reconcile_success_path_supersede(tmp_path: Path):
    gate = HttpJevReconcileGate(api_key="k")
    eng, q, ledger = _engine(tmp_path, gate)
    ledger.upsert("user.weather.local", {"condition": "sunny"}, source_event_id="d0")
    body = {
        "model": "jev-1.13.0",
        "answers": {
            "relation": {"type": "choice", "choice": "supersedes", "confidence": 0.92},
            "should_forget_incumbent": {"type": "noul", "noul": 0.91},
            "ttl_urgency": {"type": "score", "score": 5, "confidence": 0.8},
            "profile_worthiness": {"type": "noul", "noul": 0.2},
            "needs_human": {"type": "noul", "noul": 0.1},
            "salience_tier": {
                "type": "choice",
                "choice": "ephemeral",
                "confidence": 0.9,
            },
        },
    }
    with patch("httpx.Client", return_value=_mock_client(_resp(200, json_body=body))):
        result = eng.reconcile_candidate(_cand())
    assert result.applied
    assert result.action == ApplyAction.SUPERSEDE
    assert ledger.get_active("user.weather.local").value_struct["condition"] == "rainy"
    assert q.total_count() == 0


def test_http_reconcile_missing_api_key_denied_no_network(tmp_path: Path):
    gate = HttpJevReconcileGate(api_key="")
    eng, q, _ = _engine(tmp_path, gate)
    # No httpx patch needed — denied before POST
    result = eng.reconcile_candidate(_cand())
    assert result.action == ApplyAction.QUARANTINE
    assert result.fail_closed
    assert q.total_count() == 1
