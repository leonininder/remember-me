"""Outbound state redaction — secrets and bodies never leave the local process."""

from __future__ import annotations

from typing import Any

from remember_me.types import (
    SECRET_FIELD_NAMES,
    Candidate,
    RedactedCandidate,
)

# Core redacted candidate projection (no enrichment).
CORE_CANDIDATE_KEYS = frozenset(
    {
        "node_id",
        "kind",
        "tags",
        "degree",
        "last_touch",
        "local_score",
        "tokens_est",
    }
)

# JustinSun/David 2026-09-22: structured enrichment only (no free-text query).
ENRICHMENT_OUTBOUND_KEYS = frozenset(
    {
        "stub_tags",  # capped tags copy
        "intent_class",  # closed query intent enum (state-level)
        "length_bucket",  # short|medium|long (state-level)
    }
)

ALLOWED_OUTBOUND_KEYS = CORE_CANDIDATE_KEYS | ENRICHMENT_OUTBOUND_KEYS

# Positive allowlists only (David: denylist is a reproducible leak surface).
ESCALATION_SNAPSHOT_ALLOWLIST = ALLOWED_OUTBOUND_KEYS | frozenset(
    {
        "proposed_chars",
        "proposed_summary_sha256",
        "sink",
        "target",
        "salience",
        "horizon",
    }
)

EMIT_META_ALLOWLIST = frozenset(
    {
        "node_id",
        "egress_id",
        "proposed_chars",
        "proposed_summary_sha256",
    }
)

WRITEBACK_PROPOSED_ALLOWLIST = frozenset(
    {
        "node_id",
        "kind",
        "tags",
        "salience",
        "horizon",
        "tokens_est",
        "degree",
    }
)


def allowlist_snapshot(
    snapshot: dict[str, Any] | None,
    *,
    allowed: frozenset[str],
) -> dict[str, Any]:
    """Keep only positively allowlisted keys (case-insensitive match on allowlist)."""
    if not snapshot:
        return {}
    allowed_l = {a.lower() for a in allowed}
    return {k: v for k, v in snapshot.items() if str(k).lower() in allowed_l}


def summary_fingerprint(text: str) -> dict[str, Any]:
    """Replace free-text summaries with length + sha256 only (never egress body text)."""
    import hashlib

    raw = text or ""
    return {
        "proposed_chars": len(raw),
        "proposed_summary_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }



def redact_state(candidates: list[Candidate]) -> list[RedactedCandidate]:
    """Project candidates to the only fields allowed outbound to Jev.

    Explicitly drops content, secret, content_ref bodies, provenance, and any
    extra attributes. Used before every Jev call.
    """
    out: list[RedactedCandidate] = []
    for c in candidates:
        out.append(
            RedactedCandidate(
                node_id=c.node_id,
                kind=c.kind,
                tags=list(c.tags),
                degree=c.degree,
                last_touch=c.last_touch,
                local_score=c.local_score,
                tokens_est=c.tokens_est,
            )
        )
    return out


def redact_to_dicts(candidates: list[Candidate]) -> list[dict[str, Any]]:
    """Redact and return plain dicts for HTTP / FakeJev payloads."""
    return [r.model_dump(mode="json") for r in redact_state(candidates)]


def assert_no_secrets(payload: Any, *, path: str = "$") -> None:
    """Raise AssertionError if any secret-like key or obvious secret value appears.

    Used by tests and as a defensive pre-flight check before HttpJev.
    """
    if isinstance(payload, dict):
        for k, v in payload.items():
            key_l = str(k).lower()
            if key_l in SECRET_FIELD_NAMES:
                raise AssertionError(f"secret field '{k}' present at {path}")
            if key_l not in ALLOWED_OUTBOUND_KEYS and key_l in {
                "content",
                "content_ref",
                "body",
                "secret",
                "password",
                "api_key",
            }:
                raise AssertionError(f"disallowed outbound field '{k}' at {path}")
            assert_no_secrets(v, path=f"{path}.{k}")
    elif isinstance(payload, list):
        for i, item in enumerate(payload):
            assert_no_secrets(item, path=f"{path}[{i}]")
    elif isinstance(payload, str):
        lowered = payload.lower()
        banned = ("sk-", "api_key=", "password=", "secret=", "bearer ")
        for b in banned:
            if b in lowered:
                raise AssertionError(f"possible secret material at {path}: contains '{b}'")


def outbound_is_safe(payload: Any) -> bool:
    """Return True if payload passes secret/disallowed-field checks."""
    try:
        assert_no_secrets(payload)
        return True
    except AssertionError:
        return False
