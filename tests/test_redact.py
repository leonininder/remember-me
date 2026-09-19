"""Redaction: secrets never in outbound state."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from remember_me.redact import (
    ALLOWED_OUTBOUND_KEYS,
    assert_no_secrets,
    outbound_is_safe,
    redact_state,
    redact_to_dicts,
)
from remember_me.types import Candidate, NodeKind


def _cand(**kwargs) -> Candidate:
    base = dict(
        node_id="n1",
        kind=NodeKind.FACT,
        tags=["preference"],
        degree=1,
        last_touch=datetime.now(UTC),
        local_score=0.8,
        tokens_est=12,
        content="SECRET body with password=hunter2",
    )
    base.update(kwargs)
    return Candidate(**base)


def test_redact_drops_content_and_extra():
    c = _cand()
    red = redact_state([c])
    assert len(red) == 1
    d = red[0].model_dump()
    assert set(d.keys()) == ALLOWED_OUTBOUND_KEYS
    assert "content" not in d
    assert "secret" not in d
    assert "content_ref" not in d


def test_assert_no_secrets_on_redacted():
    payload = redact_to_dicts([_cand()])
    assert_no_secrets(payload)
    assert outbound_is_safe(payload)


def test_assert_no_secrets_catches_secret_field():
    with pytest.raises(AssertionError, match="secret"):
        assert_no_secrets([{"node_id": "x", "secret": "boom"}])


def test_assert_no_secrets_catches_content_field():
    with pytest.raises(AssertionError):
        assert_no_secrets([{"node_id": "x", "content": "body"}])


def test_assert_no_secrets_catches_bearer_string():
    with pytest.raises(AssertionError, match="secret material"):
        assert_no_secrets("Authorization: Bearer abc")


def test_outbound_is_safe_false():
    assert outbound_is_safe({"password": "x"}) is False
