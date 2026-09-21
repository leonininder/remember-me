"""Bake-off: ``local_topk_stub`` vs FakeJev-gated (offline) or HttpJev (live).

Offline FakeJev metrics are NON-EVIDENCE (conf ∝ local_score). Live HttpJev
metrics go to ``bakeoff_metrics_live.json`` and must be labeled LIVE evidence.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from remember_me.graph import TopologyGraph
from remember_me.jev_client import FakeJev, HttpJev
from remember_me.pipeline import MemoryPipeline
from remember_me.retrieve import LocalCandidateRetriever
from remember_me.types import JEV_MODEL_PIN, Horizon, HydrateAction, Marker, NodeKind

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
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    mean_hydrated: float = 0.0
    jev_calls: int = 0
    fail_closed_rate: float = 0.0
    escalate_rate: float = 0.0
    jev_model: str | None = None
    usage_tokens: dict[str, Any] = field(default_factory=dict)


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


def run_local_topk_stub(
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
        latencies.append((time.perf_counter() - t0) * 1000)
        p, r = _precision_recall(ids, case.relevant_ids, k)
        precs.append(p)
        recalls.append(r)
        over = len(set(ids) & set(case.overshare_ids))
        overshares.append(1.0 if over else 0.0)
        hydrated_counts.append(len(ids))

    return BakeoffMetrics(
        mode="local_topk_stub",
        n_queries=len(cases),
        precision_at_k=sum(precs) / len(precs) if precs else 0.0,
        recall_at_k=sum(recalls) / len(recalls) if recalls else 0.0,
        overshare_rate=sum(overshares) / len(overshares) if overshares else 0.0,
        mean_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        p50_latency_ms=_percentile(latencies, 50),
        p95_latency_ms=_percentile(latencies, 95),
        mean_hydrated=sum(hydrated_counts) / len(hydrated_counts) if hydrated_counts else 0.0,
        jev_calls=0,
        fail_closed_rate=0.0,
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
    fail_closed = 0
    escalate_n = 0
    decision_n = 0

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
        for d in result.decisions:
            decision_n += 1
            if d.fail_closed:
                fail_closed += 1
            if d.action == HydrateAction.ESCALATE_HUMAN:
                escalate_n += 1

    return BakeoffMetrics(
        mode="jev_gated",
        n_queries=len(cases),
        precision_at_k=sum(precs) / len(precs) if precs else 0.0,
        recall_at_k=sum(recalls) / len(recalls) if recalls else 0.0,
        overshare_rate=sum(overshares) / len(overshares) if overshares else 0.0,
        mean_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        p50_latency_ms=_percentile(latencies, 50),
        p95_latency_ms=_percentile(latencies, 95),
        mean_hydrated=sum(hydrated_counts) / len(hydrated_counts) if hydrated_counts else 0.0,
        jev_calls=client.call_count,
        fail_closed_rate=(fail_closed / decision_n) if decision_n else 0.0,
        escalate_rate=(escalate_n / decision_n) if decision_n else 0.0,
        jev_model=client.model_pin,
    )


def run_jev_gated_live(
    graph: TopologyGraph,
    cases: list[QueryCase],
    *,
    k: int = 5,
    timeout_s: float = 60.0,
    api_key: str | None = None,
) -> BakeoffMetrics:
    """Live HttpJev path: retrieve → redact → System One → policy hydrate.

    Requires ``TYPESAFE_API_KEY``. Prefer ``batch_candidates=True`` (HttpJev default).
    On HTTP 429 the client fail-closes (timed_out); rate-limit is counted in fail_closed.
    """
    key = api_key or os.environ.get("TYPESAFE_API_KEY", "")
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY required for live bake-off")

    client = HttpJev(
        api_key=key,
        timeout_s=timeout_s,
        batch_candidates=True,
        model_pin=JEV_MODEL_PIN,
    )
    pipe = MemoryPipeline(graph, client, top_k=k)
    latencies: list[float] = []
    precs: list[float] = []
    recalls: list[float] = []
    overshares: list[float] = []
    hydrated_counts: list[int] = []
    fail_closed = 0
    escalate_n = 0
    decision_n = 0
    usage_acc: dict[str, int] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    rate_limited = 0

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
        for d in result.decisions:
            decision_n += 1
            if d.fail_closed:
                fail_closed += 1
                if "429" in (d.reason or ""):
                    rate_limited += 1
            if d.action == HydrateAction.ESCALATE_HUMAN:
                escalate_n += 1
        if client.last_usage and isinstance(client.last_usage, dict):
            for tok_key in ("input_tokens", "output_tokens", "total_tokens"):
                val = client.last_usage.get(tok_key)
                if isinstance(val, (int, float)):
                    usage_acc[tok_key] = usage_acc.get(tok_key, 0) + int(val)

    usage_out: dict[str, Any] = {k: v for k, v in usage_acc.items() if v}
    if rate_limited:
        usage_out["rate_limited_decisions"] = rate_limited

    return BakeoffMetrics(
        mode="jev_gated_live",
        n_queries=len(cases),
        precision_at_k=sum(precs) / len(precs) if precs else 0.0,
        recall_at_k=sum(recalls) / len(recalls) if recalls else 0.0,
        overshare_rate=sum(overshares) / len(overshares) if overshares else 0.0,
        mean_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        p50_latency_ms=_percentile(latencies, 50),
        p95_latency_ms=_percentile(latencies, 95),
        mean_hydrated=sum(hydrated_counts) / len(hydrated_counts) if hydrated_counts else 0.0,
        jev_calls=client.call_count,
        fail_closed_rate=(fail_closed / decision_n) if decision_n else 0.0,
        escalate_rate=(escalate_n / decision_n) if decision_n else 0.0,
        jev_model=client.last_response_model or client.model_pin,
        usage_tokens=usage_out,
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

    baseline = run_local_topk_stub(graph, cases, k=k)
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
            "Offline FakeJev bake-off. PREVIEW ONLY / NON-EVIDENCE. "
            "Jev is decision gate after local retrieval — not the ranker."
        ),
    }

    out_path = out_path or Path("bakeoff_metrics.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def run_bakeoff_live(
    *,
    fixtures_dir: Path | None = None,
    out_path: Path | None = None,
    k: int = 5,
    timeout_s: float = 60.0,
) -> dict[str, Any]:
    """Arms B (local_topk_stub) vs C (jev_gated_live). Writes bakeoff_metrics_live.json."""
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise RuntimeError(
            "TYPESAFE_API_KEY not set — refuse live bake-off (use FakeJev offline bakeoff)"
        )

    fixtures_dir = fixtures_dir or FIXTURES_DIR
    graph = load_markers(fixtures_dir / "markers.json")
    cases = load_queries(fixtures_dir / "queries.json")
    if len(cases) < 50:
        raise RuntimeError(f"expected >=50 queries, got {len(cases)}")

    baseline = run_local_topk_stub(graph, cases, k=k)
    gated = run_jev_gated_live(graph, cases, k=k, timeout_s=timeout_s)

    # Pre-registered bars (docs/reviews/LIVE_PILOT_RECAL_2026-09-22.md) — evaluate after run.
    prec_bar = gated.precision_at_k >= (baseline.precision_at_k - 0.05)
    over_bar = gated.overshare_rate <= baseline.overshare_rate + 1e-12
    fail_bar = gated.fail_closed_rate <= 0.05
    bars_clear = bool(prec_bar and over_bar and fail_bar)
    report: dict[str, Any] = {
        "label": "LIVE HttpJev evidence (not FakeJev)",
        "promotion_status": "PROMOTE_CANDIDATE" if bars_clear else "NON_PROMOTE",
        "enrichment": {
            "include_raw_query": False,
            "keys": ["intent_class", "length_bucket", "stub_tags"],
            "thresholds": {"T_ACCEPT": 0.85, "T_ESCALATE": 0.55},
            "note": "Thresholds unchanged; enrichment-first (David/JustinSun 2026-09-22)",
        },
        "pre_registered_bars": {
            "precision_at_k_C_ge_B_minus_0.05": prec_bar,
            "overshare_rate_C_le_B": over_bar,
            "fail_closed_rate_C_le_0.05": fail_bar,
            "bars_clear": bars_clear,
            "note": (
                "skip→admit alone does not clear ≥9.5; "
                "precision/overshare/fail_closed required"
            ),
        },
        "k": k,
        "n_queries": len(cases),
        "fixtures": str(fixtures_dir),
        "model_pin": JEV_MODEL_PIN,
        "baseline": asdict(baseline),
        "jev_gated_live": asdict(gated),
        "deltas": {
            "precision_at_k": gated.precision_at_k - baseline.precision_at_k,
            "recall_at_k": gated.recall_at_k - baseline.recall_at_k,
            "overshare_rate": gated.overshare_rate - baseline.overshare_rate,
            "p50_latency_ms": gated.p50_latency_ms - baseline.p50_latency_ms,
            "p95_latency_ms": gated.p95_latency_ms - baseline.p95_latency_ms,
            "fail_closed_rate": gated.fail_closed_rate - baseline.fail_closed_rate,
            "escalate_rate": gated.escalate_rate - baseline.escalate_rate,
        },
        "notes": (
            "LIVE TypeSafe System One bake-off (HttpJev) after structured enrichment. "
            "Arms: B=local_topk_stub vs C=jev_gated_live. "
            "FakeJev bakeoff_metrics.json remains NON-EVIDENCE. "
            "Do not claim acceleration unless bars_clear and latency supports it."
        ),
    }

    out_path = out_path or Path("bakeoff_metrics_live.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
