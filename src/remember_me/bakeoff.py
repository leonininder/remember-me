"""Offline bake-off: Hindsight-stub-only vs Jev-gated hydrate (50 synthetic queries).

Metrics: precision@k, overshare proxy, latency. Writes JSON report.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from remember_me.graph import TopologyGraph
from remember_me.jev_client import FakeJev
from remember_me.pipeline import MemoryPipeline
from remember_me.retrieve import LocalCandidateRetriever
from remember_me.types import Horizon, HydrateAction, Marker, NodeKind

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "personal_prefs"


@dataclass
class QueryCase:
    query_id: str
    query: str
    relevant_ids: list[str]
    overshare_ids: list[str]


@dataclass
class BakeoffMetrics:
    mode: str
    n_queries: int
    precision_at_k: float
    recall_at_k: float
    overshare_rate: float
    mean_latency_ms: float
    p95_latency_ms: float
    mean_hydrated: float
    jev_calls: int


def load_markers(path: Path | None = None) -> TopologyGraph:
    path = path or (FIXTURES_DIR / "markers.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    g = TopologyGraph()
    for raw in data["markers"]:
        g.upsert(
            Marker(
                node_id=raw["node_id"],
                kind=NodeKind(raw.get("kind", "fact")),
                horizon=Horizon(raw.get("horizon", "working")),
                content_ref=raw.get("content_ref", f"local://{raw['node_id']}"),
                content=raw.get("content", ""),
                tags=list(raw.get("tags", [])),
                salience=float(raw.get("salience", 0.5)),
                provenance=raw.get("provenance", "fixture"),
            ),
            apply_default_ttl=True,
        )
    return g


def load_queries(path: Path | None = None) -> list[QueryCase]:
    path = path or (FIXTURES_DIR / "queries.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        QueryCase(
            query_id=q["id"],
            query=q["query"],
            relevant_ids=list(q.get("relevant_ids", [])),
            overshare_ids=list(q.get("overshare_ids", [])),
        )
        for q in data["queries"]
    ]


def _precision_recall(
    hydrated_ids: list[str], relevant: list[str], k: int
) -> tuple[float, float]:
    top = hydrated_ids[:k]
    if not top:
        return 0.0, 0.0
    hit = len(set(top) & set(relevant))
    prec = hit / len(top)
    rec = hit / len(relevant) if relevant else 0.0
    return prec, rec


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return s[idx]


def run_hindsight_stub(
    graph: TopologyGraph, cases: list[QueryCase], *, k: int = 5
) -> BakeoffMetrics:
    """Baseline: local retrieve only; hydrate top-k stubs (no Jev)."""
    retriever = LocalCandidateRetriever(graph, top_k=k)
    latencies: list[float] = []
    precs: list[float] = []
    recalls: list[float] = []
    overshares: list[float] = []
    hydrated_counts: list[int] = []

    for case in cases:
        t0 = time.perf_counter()
        cands = retriever.retrieve(case.query, top_k=k)
        ids = [c.node_id for c in cands]
        # Stub-only: treat all retrieved as "hydrated" stubs (Hindsight-only path).
        latencies.append((time.perf_counter() - t0) * 1000)
        p, r = _precision_recall(ids, case.relevant_ids, k)
        precs.append(p)
        recalls.append(r)
        over = len(set(ids) & set(case.overshare_ids))
        overshares.append(1.0 if over else 0.0)
        hydrated_counts.append(len(ids))

    return BakeoffMetrics(
        mode="hindsight_stub_only",
        n_queries=len(cases),
        precision_at_k=sum(precs) / len(precs) if precs else 0.0,
        recall_at_k=sum(recalls) / len(recalls) if recalls else 0.0,
        overshare_rate=sum(overshares) / len(overshares) if overshares else 0.0,
        mean_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        p95_latency_ms=_percentile(latencies, 95),
        mean_hydrated=sum(hydrated_counts) / len(hydrated_counts) if hydrated_counts else 0.0,
        jev_calls=0,
    )


def run_jev_gated(
    graph: TopologyGraph, cases: list[QueryCase], *, k: int = 5
) -> BakeoffMetrics:
    """Jev-gated path: retrieve → redact → FakeJev → policy hydrate."""
    client = FakeJev()
    pipe = MemoryPipeline(graph, client, top_k=k)
    latencies: list[float] = []
    precs: list[float] = []
    recalls: list[float] = []
    overshares: list[float] = []
    hydrated_counts: list[int] = []

    for case in cases:
        t0 = time.perf_counter()
        result = pipe.run(case.query, top_k=k)
        ids = [
            h.node_id
            for h in result.hydrated
            if h.action in (HydrateAction.HYDRATE_FULL, HydrateAction.STUB_ONLY)
        ]
        latencies.append((time.perf_counter() - t0) * 1000)
        p, r = _precision_recall(ids, case.relevant_ids, k)
        precs.append(p)
        recalls.append(r)
        over = len(set(ids) & set(case.overshare_ids))
        overshares.append(1.0 if over else 0.0)
        hydrated_counts.append(len(ids))

    return BakeoffMetrics(
        mode="jev_gated",
        n_queries=len(cases),
        precision_at_k=sum(precs) / len(precs) if precs else 0.0,
        recall_at_k=sum(recalls) / len(recalls) if recalls else 0.0,
        overshare_rate=sum(overshares) / len(overshares) if overshares else 0.0,
        mean_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        p95_latency_ms=_percentile(latencies, 95),
        mean_hydrated=sum(hydrated_counts) / len(hydrated_counts) if hydrated_counts else 0.0,
        jev_calls=client.call_count,
    )


def run_bakeoff(
    *,
    fixtures_dir: Path | None = None,
    out_path: Path | None = None,
    k: int = 5,
) -> dict[str, Any]:
    fixtures_dir = fixtures_dir or FIXTURES_DIR
    graph = load_markers(fixtures_dir / "markers.json")
    cases = load_queries(fixtures_dir / "queries.json")
    if len(cases) < 50:
        raise RuntimeError(f"expected >=50 queries, got {len(cases)}")

    baseline = run_hindsight_stub(graph, cases, k=k)
    gated = run_jev_gated(graph, cases, k=k)

    report: dict[str, Any] = {
        "k": k,
        "n_queries": len(cases),
        "fixtures": str(fixtures_dir),
        "baseline": asdict(baseline),
        "jev_gated": asdict(gated),
        "deltas": {
            "precision_at_k": gated.precision_at_k - baseline.precision_at_k,
            "recall_at_k": gated.recall_at_k - baseline.recall_at_k,
            "overshare_rate": gated.overshare_rate - baseline.overshare_rate,
            "p95_latency_ms": gated.p95_latency_ms - baseline.p95_latency_ms,
        },
        "notes": (
            "Offline FakeJev bake-off. PREVIEW ONLY. "
            "Jev is decision gate after local retrieval — not the ranker."
        ),
    }

    out_path = out_path or Path("bakeoff_metrics.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
