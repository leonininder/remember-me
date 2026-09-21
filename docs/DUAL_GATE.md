# Dual-gate hardening — remember-me

**One-liner:** Local candidates first. Jev never ranks. Jev only admits.

**Written:** 2026-09-21 (CST / Asia/Taipei) · aligns with [PHASE_9_5_PLAN.md](PHASE_9_5_PLAN.md)

---

## Two gates after local recall

| Gate | Question | Fail-closed |
|------|----------|-------------|
| **Ingress (hydrate)** | What may enter the LLM context? | `skip` (optional local stub) |
| **Egress (emit)** | What may leave the local boundary? | `deny_emit` / `block` |
| **Writeback** | What may hit durable LTM / wiki? | `deny_writeback` |
| **Admit** | What may enter the local graph? | `defer` |

Jev answers typed Choice / Score / Noul only. It does **not** reorder candidates or replace `local_score`.

---

## Ingress: first-class `escalate_human`

| Confidence | Hydrate action |
|------------|----------------|
| ≥ 0.85 (`T_ACCEPT`) | Accept Choice (`hydrate_full` / `promote_durable` / …) |
| 0.55–0.85 (`T_ESCALATE`) | **`escalate_human`** (+ `EscalationRecord`) — not silent stub alone |
| < 0.55 | `skip` |
| timeout / deny / malformed | fail-closed → `skip` |

Conflicts (e.g. high-conf full hydrate + `still_matters=false`) also → `escalate_human`.

`PipelineResult.escalations` and `escalate_human_count` surface handoffs. Escalated nodes are **not** auto full-hydrated into the LLM.

---

## Egress APIs

```python
from remember_me import DualGatePipeline, FakeJev, TopologyGraph

pipe = DualGatePipeline(TopologyGraph(), FakeJev())
ingress = pipe.run("What is my UI theme?")
egress = pipe.run_egress(
    "Redacted prefs summary…",
    {"hydrated_ids": [h.node_id for h in ingress.hydrated]},
    sink="agent_channel",
)
# or: pipe.run_dual(query, egress_summary="…")
```

- `EmitEgressGate` / `EmitGate` → `decide_emit(sink=…, payload_meta=…)`
- `WritebackGate` → `decide_writeback(target=…, proposed=…)` — never send `content` / secrets
- Policy: mid-band emit/writeback → `escalate_human`; errors → deny (never silent allow)

Optional Nouls on emit: `leak_risk`, `on_topic`.

---

## Fan-out defaults

`FANOUT_DEFAULTS` (`remember_me.fanout`): `batch_candidates=True`, `include_raw_query=False`, core hydrate Q IDs frozen. FakeJev and HttpJev batch multi-candidate × multi-question in **one** `decide_hydrate` call.

---

## No-rerank contract

After local retrieve, candidate **order** and each **`local_score`** are immutable through redact → Jev → policy. See `assert_no_rerank` and `tests/test_no_rerank.py`.

---

## CLI

```bash
remember-me demo          # ingress decisions + egress decision
remember-me demo-dual     # DualGatePipeline (emit + writeback wired)
```

---

## Honesty

Offline FakeJev proves the API and fail-closed paths. Live TypeSafe pilot logs are still required before any SCORECARD ≥9.0 / ≥9.5 claim. See [SCORECARD.md](../SCORECARD.md) and [REVIEW_PACKET.md](REVIEW_PACKET.md).
