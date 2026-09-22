"""Ontology load + FactKey minting (PLAN §4.2.1 / §4.3)."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_COMPONENT_RE = re.compile(r"[^a-z0-9_]+")
_MULTI_US = re.compile(r"_+")

MAX_COMPONENT_LEN = 64
MAX_FACT_KEY_LEN = 192


def default_ontology_path() -> Path:
    """Repo fixture path: fixtures/memorybench_tfl/schema/ontology_v0.json."""
    # src/remember_me/tfl/ontology.py → parents[3] = repo root
    return (
        Path(__file__).resolve().parents[3]
        / "fixtures"
        / "memorybench_tfl"
        / "schema"
        / "ontology_v0.json"
    )


def normalize_component(raw: str, *, max_len: int = MAX_COMPONENT_LEN) -> str:
    """NFKC → lowercase → non [a-z0-9_] → _; collapse __; trim _; cap length."""
    s = unicodedata.normalize("NFKC", str(raw)).lower()
    s = _COMPONENT_RE.sub("_", s)
    s = _MULTI_US.sub("_", s).strip("_")
    if len(s) > max_len:
        s = s[:max_len].rstrip("_")
    return s


def normalize_fact_key(raw: str) -> str:
    parts = [normalize_component(p) for p in str(raw).split(".") if p]
    parts = [p for p in parts if p]
    key = ".".join(parts)
    if len(key) > MAX_FACT_KEY_LEN:
        key = key[:MAX_FACT_KEY_LEN].rstrip("._")
    return key


@dataclass(frozen=True)
class AttributeSpec:
    name: str
    qualifiers: tuple[str, ...]
    value_schema: dict[str, Any]


@dataclass(frozen=True)
class Ontology:
    ontology_id: str
    entities: frozenset[str]
    attributes: dict[str, dict[str, AttributeSpec]]  # entity -> attr -> spec
    fact_key_examples: tuple[str, ...]

    @classmethod
    def load(cls, path: str | Path | None = None) -> Ontology:
        p = Path(path) if path else default_ontology_path()
        data = json.loads(p.read_text(encoding="utf-8"))
        attrs: dict[str, dict[str, AttributeSpec]] = {}
        raw_attrs = data.get("attributes") or {}
        for entity, ent_map in raw_attrs.items():
            attrs[entity] = {}
            for attr_name, spec in (ent_map or {}).items():
                attrs[entity][attr_name] = AttributeSpec(
                    name=attr_name,
                    qualifiers=tuple(spec.get("qualifiers") or []),
                    value_schema=dict(spec.get("value_schema") or {}),
                )
        return cls(
            ontology_id=str(data.get("ontology_id") or "tfl_ontology_v0"),
            entities=frozenset(data.get("entities") or []),
            attributes=attrs,
            fact_key_examples=tuple(data.get("fact_key_examples") or []),
        )

    def get_attr(self, entity: str, attribute: str) -> AttributeSpec | None:
        return self.attributes.get(entity, {}).get(attribute)

    def is_domain_entity(self, entity: str) -> bool:
        return entity in self.entities and entity != "quarantine"


class FactKeyMintError(ValueError):
    """Illegal FactKey mint target (e.g. bare weather.*)."""


def mint_fact_key(
    entity: str,
    attribute: str,
    qualifier: str | None = None,
    *,
    ontology: Ontology | None = None,
    allow_quarantine_bucket: bool = True,
) -> str:
    """Mint canonical FactKey = entity.attribute[.qualifier].

    Domain examples must be under ``user.*`` / ``agent.*`` / ``quarantine.*``.
    Bare ``weather.*`` / ``insects.*`` are illegal mint targets.
    Unknown ontology paths → quarantine bucket when allowed.
    """
    ont = ontology or Ontology.load()
    e = normalize_component(entity)
    a = normalize_component(attribute)
    q = normalize_component(qualifier) if qualifier else None

    if not e or not a:
        raise FactKeyMintError("entity and attribute required after normalize")

    # Bare domain stems without owner namespace are illegal.
    if e in {"weather", "insects", "home", "pref"}:
        raise FactKeyMintError(
            f"bare '{e}.*' is illegal; use user.{e}.* (David R2 #3)"
        )

    if e == "quarantine":
        key = f"quarantine.{a}" + (f".{q}" if q else "")
        return normalize_fact_key(key)

    if e not in ont.entities:
        if not allow_quarantine_bucket:
            raise FactKeyMintError(f"unknown entity '{e}'")
        return quarantine_bucket_key(e, a, q)

    spec = ont.get_attr(e, a)
    if spec is None:
        if not allow_quarantine_bucket:
            raise FactKeyMintError(f"unknown attribute '{e}.{a}'")
        return quarantine_bucket_key(e, a, q)

    if q is not None and spec.qualifiers and q not in spec.qualifiers:
        if not allow_quarantine_bucket:
            raise FactKeyMintError(f"unknown qualifier '{q}' for {e}.{a}")
        return quarantine_bucket_key(e, a, q)

    if q is None and spec.qualifiers:
        # Qualifier required when ontology lists them — route to quarantine.
        if not allow_quarantine_bucket:
            raise FactKeyMintError(f"qualifier required for {e}.{a}")
        return quarantine_bucket_key(e, a, None)

    parts = [e, a] + ([q] if q else [])
    key = ".".join(parts)
    return normalize_fact_key(key)


def quarantine_bucket_key(
    entity: str | None = None,
    attribute: str | None = None,
    qualifier: str | None = None,
    *,
    raw_seed: str | None = None,
) -> str:
    """``quarantine.<hash8>`` or ``quarantine.<entity>.<attr>``."""
    if entity and attribute:
        e = normalize_component(entity) or "x"
        a = normalize_component(attribute) or "x"
        key = f"quarantine.{e}.{a}"
        if qualifier:
            q = normalize_component(qualifier)
            if q:
                key = f"{key}.{q}"
        return normalize_fact_key(key)[:MAX_FACT_KEY_LEN]
    seed = raw_seed or f"{entity}|{attribute}|{qualifier}"
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    return f"quarantine.{h}"


def fact_key_hash16(fact_key: str) -> str:
    return hashlib.sha256(fact_key.encode("utf-8")).hexdigest()[:16]
