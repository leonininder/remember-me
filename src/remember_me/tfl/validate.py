"""CandidateFact + value_struct closed admit validation (PLAN §4.2)."""

from __future__ import annotations

from typing import Any

from remember_me.tfl.canonical import canonical_bytes
from remember_me.tfl.ontology import (
    Ontology,
    mint_fact_key,
)
from remember_me.tfl.types import (
    FORBIDDEN_SOLE_VALUE_KEYS,
    VALUE_STRUCT_MAX_BYTES,
    VALUE_STRUCT_MAX_DEPTH,
    VALUE_STRUCT_MAX_STRING,
    CandidateFact,
    ValidationResult,
)


def _depth(obj: Any, cur: int = 0) -> int:
    if isinstance(obj, dict):
        if not obj:
            return cur
        return max(_depth(v, cur + 1) for v in obj.values())
    if isinstance(obj, list):
        if not obj:
            return cur
        return max(_depth(v, cur + 1) for v in obj)
    return cur


def _check_strings(obj: Any, path: str = "") -> str | None:
    if isinstance(obj, str):
        if len(obj) > VALUE_STRUCT_MAX_STRING:
            return f"string at {path or '$'} exceeds {VALUE_STRUCT_MAX_STRING} chars"
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            err = _check_strings(v, f"{path}.{k}" if path else str(k))
            if err:
                return err
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            err = _check_strings(v, f"{path}[{i}]")
            if err:
                return err
    return None


def validate_value_struct_caps(value_struct: dict[str, Any]) -> str | None:
    """Global caps: depth≤3, strings≤128, ≤2048B canonical, no sole prose keys."""
    if not isinstance(value_struct, dict):
        return "value_struct must be an object"
    if _depth(value_struct) > VALUE_STRUCT_MAX_DEPTH:
        return f"value_struct depth exceeds {VALUE_STRUCT_MAX_DEPTH}"
    err = _check_strings(value_struct)
    if err:
        return err
    raw = canonical_bytes(value_struct)
    if len(raw) > VALUE_STRUCT_MAX_BYTES:
        return f"value_struct exceeds {VALUE_STRUCT_MAX_BYTES} bytes canonical UTF-8"
    keys = set(value_struct.keys())
    if keys and keys.issubset(FORBIDDEN_SOLE_VALUE_KEYS):
        return (
            "value_struct sole keys may not be only "
            f"{sorted(FORBIDDEN_SOLE_VALUE_KEYS)} (diary prose forbidden as SoT)"
        )
    if len(keys) == 1:
        sole = next(iter(keys))
        if sole in FORBIDDEN_SOLE_VALUE_KEYS:
            return f"forbidden sole value_struct key '{sole}'"
    return None


def _type_ok(val: Any, expected: str) -> bool:
    mapping = {
        "object": dict,
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "null": type(None),
    }
    t = mapping.get(expected)
    if t is None:
        return True
    if expected == "number" and isinstance(val, bool):
        return False
    if expected == "integer" and isinstance(val, bool):
        return False
    return isinstance(val, t)


def validate_against_schema(value: Any, schema: dict[str, Any], path: str = "$") -> str | None:
    """Minimal JSON-Schema subset used by ontology_v0 value_schema."""
    if not schema:
        return None
    stype = schema.get("type")
    if stype and not _type_ok(value, stype):
        return f"{path}: expected type {stype}"

    if "enum" in schema and value not in schema["enum"]:
        return f"{path}: value not in enum {schema['enum']}"

    if "maxLength" in schema and isinstance(value, str) and len(value) > schema["maxLength"]:
        return f"{path}: maxLength {schema['maxLength']} exceeded"

    if stype == "object" or isinstance(value, dict):
        if not isinstance(value, dict):
            return f"{path}: expected object"
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        for req in required:
            if req not in value:
                return f"{path}: missing required '{req}'"
        additional = schema.get("additionalProperties", True)
        for k, v in value.items():
            if k in props:
                err = validate_against_schema(v, props[k], f"{path}.{k}")
                if err:
                    return err
            elif additional is False:
                return f"{path}: additional property '{k}' not allowed"
            elif isinstance(additional, dict):
                err = validate_against_schema(v, additional, f"{path}.{k}")
                if err:
                    return err
    return None


def validate_candidate(
    raw: dict[str, Any] | CandidateFact,
    *,
    ontology: Ontology | None = None,
) -> ValidationResult:
    """Schema-validate CandidateFact, ontology allowlist, mint FactKey.

    Invalid / unknown → quarantine routing (never prose SoT).
    """
    ont = ontology or Ontology.load()
    try:
        cand = (
            raw
            if isinstance(raw, CandidateFact)
            else CandidateFact.model_validate(raw)
        )
    except Exception as exc:  # noqa: BLE001 — admit path fail-closed
        return ValidationResult(
            ok=False,
            reason=f"schema_reject: {exc}",
            quarantine=True,
        )

    caps_err = validate_value_struct_caps(cand.value_struct)
    if caps_err:
        return ValidationResult(
            ok=False,
            candidate=cand,
            reason=f"value_struct_caps: {caps_err}",
            quarantine=True,
        )

    # Ontology attribute schema when known
    entity_n = cand.entity.strip().lower()
    attr_n = cand.attribute.strip().lower()
    spec = ont.get_attr(entity_n, attr_n)
    if spec and spec.value_schema:
        schema_err = validate_against_schema(cand.value_struct, spec.value_schema)
        if schema_err:
            return ValidationResult(
                ok=False,
                candidate=cand,
                reason=f"ontology_value_schema: {schema_err}",
                quarantine=True,
                fact_key=_safe_quarantine_key(cand),
            )

    try:
        key = mint_fact_key(
            cand.entity,
            cand.attribute,
            cand.qualifier,
            ontology=ont,
            allow_quarantine_bucket=True,
        )
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(
            ok=False,
            candidate=cand,
            reason=f"mint_reject: {exc}",
            quarantine=True,
            fact_key=_safe_quarantine_key(cand),
        )

    # If minted into quarantine.* because unknown path → not ok for ledger auto-admit
    if key.startswith("quarantine."):
        return ValidationResult(
            ok=False,
            candidate=cand,
            fact_key=key,
            reason="ontology_unknown_or_illegal_path",
            quarantine=True,
        )

    # proposed_fact_key ignored unless it matches minted ontology path
    if cand.proposed_fact_key:
        from remember_me.tfl.ontology import normalize_fact_key

        proposed = normalize_fact_key(cand.proposed_fact_key)
        if proposed != key:
            # ignore mismatched proposal; keep minted key
            pass

    return ValidationResult(ok=True, fact_key=key, candidate=cand, reason="accepted")


def _safe_quarantine_key(cand: CandidateFact) -> str:
    from remember_me.tfl.ontology import quarantine_bucket_key

    return quarantine_bucket_key(cand.entity, cand.attribute, cand.qualifier)
