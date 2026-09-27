"""Local candidate retrieval — keyword/tag/recency mock of TEMPR.

Jev is NEVER used as a similarity ranker here.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

from remember_me.graph import TopologyGraph
from remember_me.types import Candidate, Marker

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_CJK = "\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002fa1f"
_SCRIPT_RE = re.compile(f"[{_CJK}]+|[^{_CJK}]+")
_CJK_RE = re.compile(f"^[{_CJK}]+$")


def tokenize(text: str) -> set[str]:
    """Unicode words plus overlapping CJK bigrams; lexical, not semantic search."""
    tokens: set[str] = set()
    for word in _TOKEN_RE.findall(text or ""):
        for part in _SCRIPT_RE.findall(word.casefold()):
            if _CJK_RE.fullmatch(part):
                tokens.update(part[i:i + 2] for i in range(max(1, len(part) - 1)))
            elif len(part) > 1:
                tokens.add(part)
    return tokens


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 16
    return max(8, len(text.split()))


class LocalCandidateRetriever:
    """Keyword + tag + recency + salience scorer (local only)."""

    def __init__(
        self,
        graph: TopologyGraph,
        *,
        top_k: int = 8,
        recency_half_life_hours: float = 24.0,
    ) -> None:
        self.graph = graph
        self.top_k = top_k
        self.recency_half_life_hours = recency_half_life_hours

    def retrieve(self, query: str, *, top_k: int | None = None) -> list[Candidate]:
        k = top_k if top_k is not None else self.top_k
        q_tokens = tokenize(query)
        # Only a truly blank query opts into the legacy recency view. Unsupported
        # non-empty input must never silently retrieve unrelated memories.
        if query.strip() and not q_tokens:
            return []
        now = datetime.now(UTC)
        scored: list[Candidate] = []
        for m in self.graph.all_markers():
            score = self._score(m, q_tokens, now)
            if score <= 0:
                continue
            scored.append(
                Candidate(
                    node_id=m.node_id,
                    kind=m.kind,
                    tags=list(m.tags),
                    degree=m.degree,
                    last_touch=m.last_touch,
                    local_score=round(score, 6),
                    tokens_est=estimate_tokens(m.content),
                    horizon=m.horizon,
                    content_ref=m.content_ref,
                    content=m.content,
                    salience=m.salience,
                )
            )
        scored.sort(key=lambda c: (c.local_score, c.last_touch), reverse=True)
        return scored[:k]

    def _score(self, marker: Marker, q_tokens: set[str], now: datetime) -> float:
        if not q_tokens:
            # Empty query → recency-only soft ranking for demos.
            text_score = 0.1
        else:
            m_tokens = tokenize(
                " ".join(
                    [
                        marker.node_id,
                        marker.kind.value,
                        " ".join(marker.tags),
                        marker.content or "",
                        marker.content_ref,
                    ]
                )
            )
            overlap = q_tokens & m_tokens
            if not overlap:
                # Soft tag partial credit
                tag_set = {t.lower() for t in marker.tags}
                overlap = q_tokens & tag_set
            if not overlap:
                return 0.0
            text_score = len(overlap) / max(len(q_tokens), 1)

        age_hours = max(0.0, (now - marker.last_touch).total_seconds() / 3600.0)
        half = max(self.recency_half_life_hours, 1e-6)
        recency = math.pow(0.5, age_hours / half)
        degree_boost = 1.0 + 0.05 * min(marker.degree, 10)
        return text_score * (0.55 + 0.35 * marker.salience + 0.1 * recency) * degree_boost
