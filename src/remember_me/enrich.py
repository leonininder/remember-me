"""Structured outbound enrichment — closed enums / buckets only (no raw query).

David / JustinSun (2026-09-22): enrich via ALLOWED_OUTBOUND_KEYS only.
Never emit query_preview unless ``include_raw_query`` is explicitly opted in.
Thresholds stay T_ACCEPT=0.85 / T_ESCALATE=0.55 until held-out calibration
shows accept-band mass for gold-hydrate cases (not noise-floor chasing).

v2 adds: intent_focus, topic_family, overlap_tag_count, intent_topic_fit,
candidate_rank_in_topk, salience_bucket, stub_token_bucket — all closed /
bounded structured signals derived locally from tag ontology + retrieve rank.
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
        "preference_safety",
        "preference_general",
        "episodic_recall",
        "sensitive_avoid",
        "other",
    }
)

# Finer closed focus (state-level) — helps separate theme vs font vs locale, etc.
INTENT_FOCUSES: frozenset[str] = frozenset(
    {
        "theme",
        "font",
        "editor",
        "language",
        "timezone",
        "docs",
        "drink",
        "notifications",
        "git",
        "testing",
        "python",
        "shell",
        "music",
        "meetings",
        "license",
        "ci",
        "safety",
        "redact",
        "model",
        "episode",
        "artifact",
        "workstyle",
        "general",
        "other",
    }
)

LENGTH_BUCKETS: frozenset[str] = frozenset({"short", "medium", "long"})
TOPIC_FAMILIES: frozenset[str] = frozenset(
    {
        "ui_theme",
        "ui_font",
        "ui_editor",
        "ui_generic",
        "locale_lang",
        "locale_tz",
        "locale_docs",
        "locale_generic",
        "food_drink",
        "workflow_git",
        "workflow_test",
        "workflow_ci",
        "workflow_generic",
        "safety",
        "python",
        "shell",
        "music",
        "meetings",
        "notifications",
        "license",
        "model",
        "episode",
        "artifact",
        "noise",
        "overshare",
        "other",
    }
)
FIT_CLASSES: frozenset[str] = frozenset(
    {"strong_match", "weak_match", "mismatch", "unknown"}
)
SALIENCE_BUCKETS: frozenset[str] = frozenset({"low", "mid", "high"})
TOKEN_BUCKETS: frozenset[str] = frozenset({"tiny", "small", "medium", "large"})

# Query-level keys allowed on System One ``state`` (never free-text query).
ALLOWED_QUERY_ENRICHMENT_KEYS: frozenset[str] = frozenset(
    {"intent_class", "intent_focus", "length_bucket"}
)

# Candidate-level enrichment keys (subset of ALLOWED_OUTBOUND_KEYS).
ALLOWED_CANDIDATE_ENRICHMENT_KEYS: frozenset[str] = frozenset(
    {
        "stub_tags",
        "topic_family",
        "overlap_tag_count",
        "intent_topic_fit",
        "candidate_rank_in_topk",
        "salience_bucket",
        "stub_token_bucket",
    }
)

_MAX_STUB_TAGS = 8
_MAX_TAG_CHARS = 32

# Ordered: first match wins. Locale before bare "ui"; safety/workflow before general.
_INTENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "sensitive_avoid",
        (
            "ssn",
            "password",
            "bank account",
            "salary",
            "credit card",
            "medical record",
            "diagnos",
            "health insurance",
        ),
    ),
    (
        "preference_locale",
        (
            "language",
            "locale",
            "timezone",
            "time zone",
            "tz",
            "chinese",
            "english",
            "trad",
            "documentation language",
            "docs language",
        ),
    ),
    (
        "preference_ui",
        (
            "theme",
            "font",
            "editor",
            "dark mode",
            "light mode",
            "monospace",
            "vim",
            "jetbrains",
            "color scheme",
        ),
    ),
    (
        "preference_food",
        (
            "coffee",
            "drink",
            "food",
            "latte",
            "tea",
            "meal",
            "oat",
            "beverage",
        ),
    ),
    (
        "preference_workflow",
        (
            "git",
            "commit",
            "branch",
            "workflow",
            "ci",
            "lint",
            "testing",
            "pytest",
            "test first",
            "conventional commit",
            "github actions",
            "before merge",
        ),
    ),
    (
        "preference_safety",
        (
            "fail closed",
            "fail-closed",
            "fail_closed",
            "redact",
            "outbound metadata",
            "model pin",
            "jev",
        ),
    ),
    (
        "preference_general",
        ("prefer", "preference", "favorite", "favourite", "like", "want"),
    ),
    (
        "episodic_recall",
        ("remember", "last time", "yesterday", "when did", "what did we", "last demo"),
    ),
)

_FOCUS_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("theme", ("theme", "dark mode", "light mode", "color scheme")),
    ("font", ("font", "monospace", "jetbrains")),
    ("editor", ("editor", "vim", "keybinding")),
    ("language", ("language", "chinese", "english", "trad", "zh")),
    ("timezone", ("timezone", "time zone", "tz", "taipei")),
    ("docs", ("documentation", "docs", "readme", "technical doc")),
    ("drink", ("drink", "coffee", "latte", "tea", "beverage", "oat")),
    ("notifications", ("notification", "mute", "evening")),
    ("git", ("git", "commit", "conventional")),
    ("testing", ("test", "pytest", "coverage", "testing")),
    ("python", ("python", "pydantic", "3.11")),
    ("shell", ("shell", "bash")),
    ("music", ("music", "lofi", "focus playlist")),
    ("meetings", ("meeting", "async")),
    ("license", ("license", "mit")),
    ("ci", ("ci", "github actions", "actions")),
    ("safety", ("fail closed", "fail-closed", "fail_closed", "safety")),
    ("redact", ("redact", "outbound")),
    ("model", ("model pin", "jev-1", "1.13")),
    ("episode", ("episode", "last demo", "demo")),
    ("artifact", ("artifact", "readme draft")),
    ("workstyle", ("workstyle", "async", "meeting")),
)

# Local tag ontology: intent_class → tags that indicate on-topic candidates.
_INTENT_TAG_ONTOLOGY: dict[str, frozenset[str]] = {
    "preference_ui": frozenset({"ui", "theme", "font", "editor", "preference"}),
    "preference_locale": frozenset({"locale", "language", "timezone", "docs", "preference"}),
    "preference_food": frozenset({"food", "drink", "preference"}),
    "preference_workflow": frozenset(
        {"workflow", "git", "testing", "procedure", "ci", "review", "preference"}
    ),
    "preference_safety": frozenset({"safety", "redact", "jev", "procedure", "model"}),
    "preference_general": frozenset({"preference"}),
    "episodic_recall": frozenset({"episode", "demo"}),
    "sensitive_avoid": frozenset({"health", "finance", "overshare"}),
    "other": frozenset(),
}

# intent_focus → preferred topic_family values for strong_match.
_FOCUS_TOPIC_STRONG: dict[str, frozenset[str]] = {
    "theme": frozenset({"ui_theme"}),
    "font": frozenset({"ui_font"}),
    "editor": frozenset({"ui_editor"}),
    "language": frozenset({"locale_lang"}),
    "timezone": frozenset({"locale_tz"}),
    "docs": frozenset({"locale_docs", "artifact"}),
    "drink": frozenset({"food_drink"}),
    "notifications": frozenset({"notifications"}),
    "git": frozenset({"workflow_git"}),
    "testing": frozenset({"workflow_test"}),
    "python": frozenset({"python"}),
    "shell": frozenset({"shell"}),
    "music": frozenset({"music"}),
    "meetings": frozenset({"meetings"}),
    "license": frozenset({"license"}),
    "ci": frozenset({"workflow_ci"}),
    "safety": frozenset({"safety"}),
    "redact": frozenset({"safety"}),
    "model": frozenset({"model"}),
    "episode": frozenset({"episode"}),
    "artifact": frozenset({"artifact"}),
    "workstyle": frozenset({"meetings"}),
    "general": frozenset(),
    "other": frozenset(),
}

# Topic family derivation: first matching tag rule wins (most specific first).
_TOPIC_TAG_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ("overshare", frozenset({"overshare", "health", "finance"})),
    ("noise", frozenset({"noise", "sports", "weather"})),
    ("ui_theme", frozenset({"theme"})),
    ("ui_font", frozenset({"font"})),
    ("ui_editor", frozenset({"editor"})),
    ("ui_generic", frozenset({"ui"})),
    ("locale_lang", frozenset({"language"})),
    ("locale_tz", frozenset({"timezone"})),
    ("locale_docs", frozenset({"docs"})),
    ("locale_generic", frozenset({"locale"})),
    ("food_drink", frozenset({"food", "drink"})),
    ("workflow_git", frozenset({"git"})),
    ("workflow_test", frozenset({"testing"})),
    ("workflow_ci", frozenset({"ci"})),
    ("workflow_generic", frozenset({"workflow", "procedure", "review"})),
    ("safety", frozenset({"safety", "redact"})),
    ("python", frozenset({"python", "runtime", "schema"})),
    ("shell", frozenset({"shell"})),
    ("music", frozenset({"music"})),
    ("meetings", frozenset({"workstyle"})),
    ("notifications", frozenset({"notifications"})),
    ("license", frozenset({"license"})),
    ("model", frozenset({"model", "jev"})),
    ("episode", frozenset({"episode", "demo"})),
    ("artifact", frozenset({"artifact"})),
)


def classify_intent(query: str) -> str:
    """Map query → closed intent_class (local only; raw query never returned)."""
    q = (query or "").lower()
    # Soft-negate: "without health" / "avoid … health" should not force sensitive.
    q_for_sensitive = q
    for neg in ("without health", "avoid health", "no health", "without finance"):
        q_for_sensitive = q_for_sensitive.replace(neg, " ")
    for label, needles in _INTENT_RULES:
        hay = q_for_sensitive if label == "sensitive_avoid" else q
        if any(n in hay for n in needles):
            return label
    return "other"


def classify_intent_focus(query: str) -> str:
    """Map query → closed intent_focus (finer than intent_class; no raw text egress)."""
    q = (query or "").lower()
    for label, needles in _FOCUS_RULES:
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


def topic_family(tags: list[str] | None) -> str:
    """Map candidate tags → closed topic_family via local ontology."""
    tag_set = {str(t).strip().lower() for t in (tags or []) if t}
    for family, needles in _TOPIC_TAG_RULES:
        if tag_set & needles:
            return family
    return "other"


def overlap_tag_count(tags: list[str] | None, intent_class: str) -> int:
    """Count candidate tags intersecting intent's local tag ontology (bounded 0..8)."""
    ontology = _INTENT_TAG_ONTOLOGY.get(intent_class, frozenset())
    if not ontology:
        return 0
    tag_set = {str(t).strip().lower() for t in (tags or []) if t}
    return min(_MAX_STUB_TAGS, len(tag_set & ontology))


def intent_topic_fit(
    *,
    intent_class: str,
    intent_focus: str,
    family: str,
    overlap: int,
) -> str:
    """Closed fit enum: does candidate topic align with query intent/focus?"""
    if family in {"noise", "overshare"}:
        if intent_class == "sensitive_avoid":
            return "strong_match"
        return "mismatch"
    strong_topics = _FOCUS_TOPIC_STRONG.get(intent_focus, frozenset())
    if strong_topics and family in strong_topics:
        return "strong_match"
    # Intent-class level alignment (weaker than focus).
    class_families: dict[str, frozenset[str]] = {
        "preference_ui": frozenset({"ui_theme", "ui_font", "ui_editor", "ui_generic"}),
        "preference_locale": frozenset(
            {"locale_lang", "locale_tz", "locale_docs", "locale_generic"}
        ),
        "preference_food": frozenset({"food_drink"}),
        "preference_workflow": frozenset(
            {"workflow_git", "workflow_test", "workflow_ci", "workflow_generic"}
        ),
        "preference_safety": frozenset({"safety", "model"}),
        "episodic_recall": frozenset({"episode"}),
    }
    aligned = class_families.get(intent_class, frozenset())
    if aligned and family in aligned:
        return "weak_match" if overlap >= 1 else "unknown"
    if overlap >= 2:
        return "weak_match"
    if overlap == 0 and intent_class not in {"other", "preference_general"}:
        return "mismatch"
    return "unknown"


def salience_bucket(salience: float | None) -> str:
    if salience is None:
        return "mid"
    if salience < 0.4:
        return "low"
    if salience < 0.75:
        return "mid"
    return "high"


def stub_token_bucket(tokens_est: int | None) -> str:
    n = int(tokens_est or 0)
    if n < 12:
        return "tiny"
    if n < 24:
        return "small"
    if n < 48:
        return "medium"
    return "large"


def query_enrichment(query: str) -> dict[str, str]:
    """Structured query-side enrichment for System One state."""
    intent = classify_intent(query)
    focus = classify_intent_focus(query)
    bucket = length_bucket(query)
    assert intent in INTENT_CLASSES
    assert focus in INTENT_FOCUSES
    assert bucket in LENGTH_BUCKETS
    return {
        "intent_class": intent,
        "intent_focus": focus,
        "length_bucket": bucket,
    }


def enrich_candidate_dict(
    candidate: dict[str, Any],
    *,
    intent_class: str = "other",
    intent_focus: str = "other",
    rank_in_topk: int | None = None,
    salience: float | None = None,
) -> dict[str, Any]:
    """Add allowlisted structured enrichment; drop unknown keys."""
    from remember_me.redact import ALLOWED_OUTBOUND_KEYS

    base = {k: v for k, v in candidate.items() if k in ALLOWED_OUTBOUND_KEYS}
    tags = base.get("tags")
    tag_list = list(tags) if isinstance(tags, list) else []
    st = stub_tags(tag_list)
    family = topic_family(tag_list)
    overlap = overlap_tag_count(tag_list, intent_class)
    fit = intent_topic_fit(
        intent_class=intent_class,
        intent_focus=intent_focus,
        family=family,
        overlap=overlap,
    )
    # Prefer explicit salience arg; else optional local-only field on dict.
    sal = salience
    if sal is None and "salience" in candidate:
        try:
            sal = float(candidate["salience"])
        except (TypeError, ValueError):
            sal = None
    tokens = base.get("tokens_est")
    try:
        tokens_i = int(tokens) if tokens is not None else None
    except (TypeError, ValueError):
        tokens_i = None

    base["stub_tags"] = st
    base["topic_family"] = family
    base["overlap_tag_count"] = overlap
    base["intent_topic_fit"] = fit
    if rank_in_topk is not None:
        base["candidate_rank_in_topk"] = max(1, int(rank_in_topk))
    base["salience_bucket"] = salience_bucket(sal)
    base["stub_token_bucket"] = stub_token_bucket(tokens_i)

    assert family in TOPIC_FAMILIES
    assert fit in FIT_CLASSES
    assert base["salience_bucket"] in SALIENCE_BUCKETS
    assert base["stub_token_bucket"] in TOKEN_BUCKETS
    return base


def enrich_candidate_dicts(
    candidates: list[dict[str, Any]],
    *,
    intent_class: str = "other",
    intent_focus: str = "other",
    saliences: list[float | None] | None = None,
) -> list[dict[str, Any]]:
    """Enrich a ranked candidate list (rank = 1-based position in list)."""
    out: list[dict[str, Any]] = []
    for i, c in enumerate(candidates):
        sal = None
        if saliences is not None and i < len(saliences):
            sal = saliences[i]
        out.append(
            enrich_candidate_dict(
                c,
                intent_class=intent_class,
                intent_focus=intent_focus,
                rank_in_topk=i + 1,
                salience=sal,
            )
        )
    return out
