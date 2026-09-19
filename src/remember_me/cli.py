"""CLI: demo, bakeoff, score-report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from remember_me.bakeoff import run_bakeoff
from remember_me.graph import TopologyGraph
from remember_me.jev_client import FakeJev
from remember_me.pipeline import MemoryPipeline
from remember_me.types import Horizon, NodeKind


def _seed_demo_graph() -> TopologyGraph:
    g = TopologyGraph()
    samples = [
        ("pref_theme", "User prefers dark theme in editors", ["preference", "ui"], 0.8),
        ("pref_lang", "Preferred spoken language is Traditional Chinese",
         ["preference", "locale"], 0.9),
        ("pref_coffee", "Morning drink preference: oat-milk latte", ["preference", "food"], 0.6),
        ("proc_commit", "Use conventional commits and small PRs", ["procedure", "git"], 0.7),
        ("fact_tz", "User timezone is Asia/Taipei (UTC+8)", ["fact", "locale"], 0.85),
        ("noise_sports", "Random sports trivia about cricket scores", ["noise"], 0.2),
        ("secret_dummy", "API key placeholder SK-DEMO-NOT-REAL", ["secret", "noise"], 0.1),
    ]
    for nid, content, tags, sal in samples:
        g.observe(
            node_id=nid,
            content=content,
            kind=NodeKind.FACT if "fact" in tags or "preference" in tags else NodeKind.PROCEDURE,
            horizon=Horizon.SESSION,
            tags=tags,
            salience=sal,
        )
    return g


def cmd_demo(_: argparse.Namespace) -> int:
    print("=== remember-me demo (offline FakeJev) ===\n")
    g = _seed_demo_graph()
    client = FakeJev()
    pipe = MemoryPipeline(g, client, top_k=5)
    query = "What are my UI and locale preferences?"
    print(f"Query: {query}\n")
    result = pipe.run(query)
    print(f"Candidates ({len(result.candidates)}):")
    for c in result.candidates:
        print(f"  - {c.node_id} score={c.local_score:.3f} tags={c.tags}")
    keys = list(result.redacted[0].model_dump().keys()) if result.redacted else []
    print(f"\nRedacted outbound keys: {keys}")
    print(f"Jev called: {result.jev_called} (client.call_count={client.call_count})")
    print("\nDecisions:")
    for d in result.decisions:
        print(f"  - {d.node_id}: {d.action.value} conf={d.confidence:.3f} ({d.reason})")
    print(f"\nHydrated ({len(result.hydrated)}):")
    for h in result.hydrated:
        preview = h.content[:80] + ("…" if len(h.content) > 80 else "")
        print(f"  - {h.node_id} [{h.action.value}] stub={h.stub}: {preview}")
    print("\nDemo complete. Secrets/bodies were not sent to Jev.")
    return 0


def cmd_bakeoff(args: argparse.Namespace) -> int:
    out = Path(args.out)
    report = run_bakeoff(out_path=out, k=args.k)
    print(json.dumps(report, indent=2))
    print(f"\nWrote metrics → {out.resolve()}", file=sys.stderr)
    return 0


def cmd_score_report(args: argparse.Namespace) -> int:
    path = Path(args.scorecard)
    if not path.exists():
        print(f"SCORECARD not found: {path}", file=sys.stderr)
        print("Run tests then generate SCORECARD.md (PREVIEW ONLY).", file=sys.stderr)
        return 1
    print(path.read_text(encoding="utf-8"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="remember-me",
        description="remember-me: local recall + TypeSafe Jev hydrate/admit decision gates",
    )
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="Offline end-to-end demo with FakeJev")
    d.set_defaults(func=cmd_demo)

    b = sub.add_parser("bakeoff", help="Run offline 50-query bake-off → metrics JSON")
    b.add_argument("--out", default="bakeoff_metrics.json", help="Output JSON path")
    b.add_argument("--k", type=int, default=5, help="precision@k cutoff")
    b.set_defaults(func=cmd_bakeoff)

    s = sub.add_parser("score-report", help="Print SCORECARD.md (PREVIEW)")
    s.add_argument(
        "--scorecard",
        default="SCORECARD.md",
        help="Path to SCORECARD.md",
    )
    s.set_defaults(func=cmd_score_report)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
