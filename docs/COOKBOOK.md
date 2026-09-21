# Cookbook — remember-me + System One

**Written:** 2026-09-20 (CST / Asia/Taipei)  
**Audience:** developers wiring a hydrate gate. No secrets. No acceleration claims.

Start in the **TypeSafe Playground**, then call System One from code. Jev is a **decision gate** (Choice / Score / Noul) — it **cannot generate prose**.

---

## 0. Playground first

1. Open the [TypeSafe docs](https://docs.typesafe.ai/) / Playground.
2. Pin a model (remember-me uses `jev-1.13.0`).
3. Send a tiny `state` + typed `questions` and read `answers` + `confidence`.
4. Only then wire `HttpJev` or the official skill.

Install the official agent skill (optional):

```bash
npx skills add typesafe-ai/skills --skill typesafe-ai
```

Docs: [https://docs.typesafe.ai/](https://docs.typesafe.ai/) · agent skill notes under the same site.

---

## 1. One System One call — memory hydrate (Choice + Score + Noul)

Adapt the usual support-ticket triage pattern to **post-recall memory hydrate**. Local TEMPR already found redacted candidates; Jev only decides what to hydrate.

### Request sketch

```json
{
  "model": "jev-1.13.0",
  "state": {
    "query_hash": "<sha256 of latest user ask>",
    "candidates": [
      {
        "node_id": "pref_theme",
        "kind": "fact",
        "tags": ["preference", "ui"],
        "degree": 1,
        "local_score": 0.82,
        "tokens_est": 24
      }
    ]
  },
  "questions": {
    "pref_theme__hydrate_action": {
      "type": "choice",
      "instructions": "[candidate pref_theme] Choose the hydrate action for this redacted memory candidate relative to the latest user ask (query_hash only unless preview present).",
      "criteria": ["hydrate_full", "stub_only", "skip", "promote_durable", "other"]
    },
    "pref_theme__need_for_next_turn": {
      "type": "score",
      "instructions": "[candidate pref_theme] How needed is this candidate for answering the latest ask on the next turn?",
      "criteria": [1, 2, 3, 4, 5]
    },
    "pref_theme__still_matters_for_latest_ask": {
      "type": "noul",
      "instructions": "[candidate pref_theme] Does this candidate still matter for the latest ask (yes ≈ hydrate consideration; no ≈ safe to skip)?"
    }
  }
}
```

`HttpJev.decide_hydrate` (default) packs **all** redacted candidates into **one** `POST /v1/systemone` with keys `{node_id}__{question_id}`. Admit stays a single-call path.

### Answer mapping (remember-me)

| Type | Mapped value | Confidence used by policy |
|------|--------------|---------------------------|
| Choice | `choice` string | `confidence` |
| Score | `score` number | `confidence` |
| Noul | `bool(noul >= 0.5)` | raw `noul` (yes-probability) |

---

## 2. Confidence routing table (policy thresholds)

Application policy owns the floors — **confidence ≠ permission to act**. remember-me defaults:

| Band | Confidence | Policy action |
|------|------------|---------------|
| **High** | ≥ **0.85** | Accept Choice → `hydrate_full` / `promote_durable` (within taxonomy) |
| **Mid** | **0.55–0.85** | **`escalate_human`** + EscalationRecord (never auto full hydrate) |
| **Low** | < **0.55** | `skip` |
| Fail | timeout / 401–403 / malformed | **Fail-closed** → `skip` (optional local stub-only for top-k) |

Same thresholds as `policy.T_ACCEPT` / `T_ESCALATE`. Noul `still_matters=false` can downgrade a high-conf full hydrate to stub.

---

## 3. Offline path (FakeJev)

```python
from remember_me import FakeJev, MemoryPipeline, TopologyGraph

g = TopologyGraph()
g.observe(node_id="pref_theme", content="User prefers dark theme",
          tags=["preference", "ui"], salience=0.9)
pipe = MemoryPipeline(g, FakeJev(), top_k=5)
result = pipe.run("What is my UI theme preference?")
assert result.jev_called
```

**FakeJev ≠ live TypeSafe.** Deterministic offline loop for CI / demo / bake-off only. See [MISCONCEPTIONS.md](MISCONCEPTIONS.md) and [HONEST_LIMITS.md](HONEST_LIMITS.md).

---

## 4. HttpJev sketch (live still unproven without a pilot log)

```python
import os
from remember_me.jev_client import HttpJev

client = HttpJev(
    api_key=os.environ["TYPESAFE_API_KEY"],
    include_raw_query=False,   # query_hash only
    batch_candidates=True,     # one POST for N candidates
)
# pipe = MemoryPipeline(graph, client, top_k=5)
```

Egress: no raw query unless `include_raw_query=True`. Bodies/secrets never leave redaction. See [RUNTIME_HOWTO.md](RUNTIME_HOWTO.md).

---

## 5. Community tutorials (orientation only)

Chinese-language community writeups (e.g. blogs such as **wangruofeng007.com**) are useful for **orientation** on System One / Jev patterns. We did **not** transcribe YouTube video [GJJq4LXHtW4](https://www.youtube.com/watch?v=GJJq4LXHtW4) — **transcripts were disabled** on that upload. Cite them as *community tutorials*, not as official TypeSafe or remember-me docs.

---


---

## 6. Dual-gate egress (emit / writeback)

**Local candidates first. Jev never ranks. Jev only admits.**

```python
from remember_me import DualGatePipeline, FakeJev, TopologyGraph

pipe = DualGatePipeline(TopologyGraph(), FakeJev(), top_k=5)
dual = pipe.run_dual(
    "What is my UI theme preference?",
    egress_summary="Redacted UI preference summary for the agent channel.",
)
print([d.action for d in dual.ingress.decisions])
print(dual.egress.decision.action if dual.egress else None)
```

- Emit Choice: `allow_emit` | `deny_emit`/`block` | `escalate_human` | `redact_further`
- Writeback Choice: `allow_writeback` | `deny_writeback` | `stage_only` | `escalate_human`
- Fail-closed on errors → deny (never silent allow). See [DUAL_GATE.md](DUAL_GATE.md).


## Related

- [DUAL_GATE.md](DUAL_GATE.md) — dual-gate egress + escalate_human
- [MISCONCEPTIONS.md](MISCONCEPTIONS.md) — common mistakes
- [GETTING_STARTED_ZH.md](GETTING_STARTED_ZH.md) — 繁中快速上手
- [HONEST_LIMITS.md](HONEST_LIMITS.md) — REAL / FAKE / CLAIMED
- [RUNTIME_HOWTO.md](RUNTIME_HOWTO.md) — FakeJev vs HttpJev
