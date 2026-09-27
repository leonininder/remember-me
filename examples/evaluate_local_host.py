"""Same-input local policy comparison. Synthetic rule checks, not model accuracy."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from remember_me.local_host import assemble_context, load_graph
from remember_me.retrieve import LocalCandidateRetriever

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("build", "alpha", {"alpha_build"}),
    ("build", "beta", {"beta_build"}),
    ("deploy", "alpha", {"alpha_deploy"}),
    ("deploy", "beta", {"beta_deploy"}),
    ("unmatched_query", "alpha", set()),
    ("build", "unknown", set()),
]


def run() -> dict:
    graph = load_graph(ROOT / "examples/host_memories.json")
    modes = {name: [] for name in ("dump_all", "local_topk", "local_scope_gate")}
    for query, scope, gold in CASES:
        for mode, rows in modes.items():
            timings = []
            for _ in range(20):
                start = time.perf_counter()
                if mode == "local_scope_gate":
                    output = assemble_context(graph, query, scope=scope, max_bytes=2048, top_k=8)
                    selected = output["audit"]["included_ids"]
                    byte_count = output["audit"]["context_bytes"]
                else:
                    records = (graph.all_markers() if mode == "dump_all"
                               else LocalCandidateRetriever(graph, top_k=8).retrieve(query))
                    selected = []
                    entries = []
                    for record in records:
                        entry = {"id": record.node_id, "text": record.content}
                        proposed = json.dumps(entries + [entry], ensure_ascii=False)
                        if len(proposed.encode("utf-8")) <= 2048:
                            selected.append(record.node_id)
                            entries.append(entry)
                    byte_count = len(json.dumps(entries, ensure_ascii=False).encode("utf-8"))
                    if not entries:
                        byte_count = 0
                timings.append((time.perf_counter() - start) * 1000)
            actual = set(selected)
            rows.append({"query": query, "scope": scope, "gold": sorted(gold),
                         "included": selected, "retained": len(actual & gold),
                         "missed": len(gold - actual), "wrongly_included": len(actual - gold),
                         "context_bytes": byte_count,
                         "latency_median_ms": statistics.median(timings),
                         "latency_max_ms": max(timings)})
    return {"label": "synthetic explicit-scope policy benchmark; no LLM or TypeSafe calls",
            "repeats_per_case": 20, "max_bytes": 2048, "top_k": 8,
            "limitations": "Hand-authored scope labels, six cases, warm local execution. "
                            "Tests policy wiring, not semantic relevance or user adoption.",
            "modes": {name: {"retained": sum(r["retained"] for r in rows),
                              "missed": sum(r["missed"] for r in rows),
                              "wrongly_included": sum(r["wrongly_included"] for r in rows),
                              "context_bytes": sum(r["context_bytes"] for r in rows),
                              "cases": rows} for name, rows in modes.items()}}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
