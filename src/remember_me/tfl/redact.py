"""TFL reconcile / escalation redaction allowlists (PLAN §4.7).

Positive allowlists only. Forbidden by default: raw diary, full transcripts,
secrets, emails, phone, exact street.
"""

from __future__ import annotations

import hashlib
from typing import Any

from remember_me.redact import allowlist_snapshot
from remember_me.tfl.canonical import canonical_json
from remember_me.tfl.types import FactVersion
from remember_me.tfl.validate import validate_value_struct_caps

# PLAN §4.7 — fields permitted in Jev reconcile state
RECONCILE_STATE_ALLOWLIST = frozenset(
    {
        "fact_key",
        "value_struct",
        "valid_from",
        "receive_ts",
        "salience_tier",
        "confidence",
        "stub_hash",
        "conflict_keys",
    }
)

# PLAN §4.7 — reconcile + escalate extras; still no raw diary
ESCALATION_SNAPSHOT_ALLOWLIST = RECONCILE_STATE_ALLOWLIST | frozenset(
    {
        "source_event_id",
        "extract_method",
        "quarantine_reason",
        "relation",
        "apply_action",
        "gate_error",
        "incumbent_version_id",
        "candidate_entity",
        "candidate_attribute",
        "candidate_qualifier",
    }
)

_FORBIDDEN_VALUE_KEYS = frozenset(
    {
        "text",
        "body",
        "prose",
        "diary",
        "notes",
        "email",
        "phone",
        "street",
        "address",
        "ssn",
        "password",
        "api_key",
        "token",
        "secret",
        "content",
    }
)

_SECRET_MARKERS = ("sk-", "api_key=", "password=", "secret=", "bearer ")


def stub_hash(value: Any) -> str:
    """Short content fingerprint for audit — never the body itself."""
    raw = canonical_json(value) if not isinstance(value, str) else value
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def clip_value_struct(value_struct: dict[str, Any] | None) -> dict[str, Any]:
    """Schema-clip value_struct for outbound: drop forbidden keys; caps enforced."""
    if not value_struct or not isinstance(value_struct, dict):
        return {}
    clipped: dict[str, Any] = {}
    for k, v in value_struct.items():
        if str(k).lower() in _FORBIDDEN_VALUE_KEYS:
            continue
        if isinstance(v, dict):
            clipped[k] = clip_value_struct(v)
        elif isinstance(v, str) and len(v) > 128:
            clipped[k] = v[:128]
        else:
            clipped[k] = v
    err = validate_value_struct_caps(clipped) if clipped else None
    if err:
        return {"_clipped": True, "stub_hash": stub_hash(value_struct)}
    return clipped


def _dt_str(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def fact_version_to_reconcile_dict(fv: FactVersion) -> dict[str, Any]:
    """Project a FactVersion to RECONCILE_STATE_ALLOWLIST fields."""
    return {
        "fact_key": fv.fact_key,
        "value_struct": clip_value_struct(fv.value_struct),
        "valid_from": _dt_str(fv.valid_from),
        "receive_ts": _dt_str(fv.receive_ts),
        "salience_tier": fv.salience_tier,
        "confidence": fv.confidence,
        "stub_hash": stub_hash(fv.value_struct),
        "conflict_keys": list(fv.conflicts_with or []),
    }


def candidate_to_reconcile_dict(
    *,
    fact_key: str,
    value_struct: dict[str, Any],
    salience_tier: str | None = None,
    confidence: float = 0.0,
    conflict_keys: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "fact_key": fact_key,
        "value_struct": clip_value_struct(value_struct),
        "valid_from": None,
        "receive_ts": None,
        "salience_tier": salience_tier,
        "confidence": confidence,
        "stub_hash": stub_hash(value_struct),
        "conflict_keys": list(conflict_keys or []),
    }


def build_reconcile_state(
    *,
    new_fact: dict[str, Any],
    incumbents: list[dict[str, Any]],
    max_incumbents: int = 5,
) -> dict[str, Any]:
    """Build outbound Jev state: new + ≤K incumbents, allowlisted only."""
    safe_new = allowlist_snapshot(new_fact, allowed=RECONCILE_STATE_ALLOWLIST)
    if "value_struct" in safe_new:
        safe_new["value_struct"] = clip_value_struct(safe_new.get("value_struct") or {})
    safe_incs: list[dict[str, Any]] = []
    for inc in incumbents[:max_incumbents]:
        s = allowlist_snapshot(inc, allowed=RECONCILE_STATE_ALLOWLIST)
        if "value_struct" in s:
            s["value_struct"] = clip_value_struct(s.get("value_struct") or {})
        safe_incs.append(s)
    return {"new": safe_new, "incumbents": safe_incs}


def build_escalation_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Positive allowlist for escalate_human / quarantine audit snapshots."""
    return allowlist_snapshot(snapshot or {}, allowed=ESCALATION_SNAPSHOT_ALLOWLIST)


def _check_str(s: str, path: str) -> None:
    lowered = s.lower()
    for b in _SECRET_MARKERS:
        if b in lowered:
            raise AssertionError(f"possible secret material at {path}: contains '{b}'")
    if "@" in s and "." in s.split("@")[-1] and " " not in s.strip():
        raise AssertionError(f"possible email at {path}")


def _assert_fact_dict(d: dict[str, Any], *, path: str) -> None:
    allowed = {a.lower() for a in RECONCILE_STATE_ALLOWLIST} | {"_clipped"}
    for k, v in d.items():
        key_l = str(k).lower()
        if key_l not in allowed:
            raise AssertionError(f"non-allowlisted reconcile field '{k}' at {path}")
        if key_l == "value_struct" and isinstance(v, dict):
            for vk in v:
                if str(vk).lower() in _FORBIDDEN_VALUE_KEYS:
                    raise AssertionError(
                        f"forbidden value_struct key '{vk}' at {path}.value_struct"
                    )
            assert_reconcile_outbound_safe(v, path=f"{path}.value_struct", _nested=True)
        else:
            assert_reconcile_outbound_safe(v, path=f"{path}.{k}", _nested=True)


def assert_reconcile_outbound_safe(
    payload: Any, *, path: str = "$", _nested: bool = False
) -> None:
    """Fail if forbidden fields / secret-like material appear in reconcile outbound."""
    if isinstance(payload, dict):
        if not _nested and path == "$":
            # Envelope: only new + incumbents
            for k, v in payload.items():
                key_l = str(k).lower()
                if key_l == "new" and isinstance(v, dict):
                    _assert_fact_dict(v, path=f"{path}.new")
                elif key_l == "incumbents" and isinstance(v, list):
                    for i, item in enumerate(v):
                        if not isinstance(item, dict):
                            raise AssertionError(f"incumbent must be object at {path}[{i}]")
                        _assert_fact_dict(item, path=f"{path}.incumbents[{i}]")
                else:
                    raise AssertionError(f"unexpected reconcile envelope key '{k}'")
            return
        for k, v in payload.items():
            assert_reconcile_outbound_safe(v, path=f"{path}.{k}", _nested=True)
    elif isinstance(payload, list):
        for i, item in enumerate(payload):
            assert_reconcile_outbound_safe(item, path=f"{path}[{i}]", _nested=True)
    elif isinstance(payload, str):
        _check_str(payload, path)
