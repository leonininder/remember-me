"""Structured outbound enrichment — closed enums / stub tags only (no raw query).

David / JustinSun (2026-09-22): enrich via ALLOWED_OUTBOUND_KEYS only
(intent_class, length_bucket, stub_tags). Never emit query_preview unless
``include_raw_query`` is explicitly opted in elsewhere. Thresholds stay
T_ACCEPT=0.85 / T_ESCALATE=0.55 until held-out calibration after enrichment.
"""

from __future__ import annotations

from typing import Any

# Closed intent taxonomy (heuristic keyword router; values are the only egress).
INTENT_CLASSES: frozenset[str] = frozenset(
    {
        "preference_ui",
        "preference_locale",
        "preference_food",
        "preference_workflow",
        "preference_general",
        "episodic_recall",
        "sensitive_avoid",
        "other",
    }
)

LENGTH_BUCKETS: frozenset[str] = frozenset({"short", "medium", "long"})

# Query-level keys allowed on System One ``state`` (never free-text query).
ALLOWED_QUERY_ENRICHMENT_KEYS: frozenset[str] = frozenset(
    {"intent_class", "length_bucket"}
)

# Candidate-level enrichment keys (subset of ALLOWED_OUTBOUND_KEYS).
ALLOWED_CANDIDATE_ENRICHMENT_KEYS: frozenset[str] = frozenset({"stub_tags"})

_MAX_STUB_TAGS = 8
_MAX_TAG_CHARS = 32

_INTENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "sensitive_avoid",
        (
            "health",
            "medical",
            "ssn",
            "password",
            "bank",
            "salary",
            "credit",
            "finance",
            "diagnos",
        ),
    ),
    (
        "preference_ui",
        ("theme", "font", "editor", "ui", "dark", "light", "monospace", "color"),
    ),
    (
        "preference_locale",
        ("language", "locale", "timezone", "tz", "chinese", "english", "trad"),
    ),
    (
        "preference_food",
        ("coffee", "drink", "food", "latte", "tea", "meal", "oat"),
    ),
    (
        "preference_workflow",
        ("git", "commit", "branch", "tool", "workflow", "ci", "lint"),
    ),
    (
        "preference_general",
        ("prefer", "preference", "favorite", "favourite", "like", "want"),
    ),
    (
        "episodic_recall",
        ("remember", "last time", "yesterday", "when did", "what did we"),
    ),
)


def classify_intent(query: str) -> str:
    """Map query → closed intent_class (local only; raw query never returned)."""
    q = (query or "").lower()
    for label, needles in _INTENT_RULES:
        if any(n in q for n in needles):
            return label
    return "other"


def length_bucket(query: str) -> str:
    """Map query char length → short|medium|long (no raw text egress)."""
    n = len(query or "")
    if n < 40:
        return "short"
    if n <= 120:
        return "medium"
    return "long"


def stub_tags(tags: list[str] | None, *, max_tags: int = _MAX_STUB_TAGS) -> list[str]:
    """Cap/normalize tags for outbound stub_tags (no content bodies)."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        t = str(raw).strip().lower()[:_MAX_TAG_CHARS]
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= max_tags:
            break
    return out


def query_enrichment(query: str) -> dict[str, str]:
    """Structured query-side enrichment for System One state."""
    intent = classify_intent(query)
    bucket = length_bucket(query)
    assert intent in INTENT_CLASSES
    assert bucket in LENGTH_BUCKETS
    return {"intent_class": intent, "length_bucket": bucket}


def enrich_candidate_dict(candidate: dict[str, Any]) -> dict[str, Any]:
    """Add stub_tags derived from allowlisted tags; drop unknown keys."""
    from remember_me.redact import ALLOWED_OUTBOUND_KEYS

    base = {k: v for k, v in candidate.items() if k in ALLOWED_OUTBOUND_KEYS}
    tags = base.get("tags")
    tag_list = list(tags) if isinstance(tags, list) else []
    base["stub_tags"] = stub_tags(tag_list)
    return base


def enrich_candidate_dicts(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_candidate_dict(c) for c in candidates]
