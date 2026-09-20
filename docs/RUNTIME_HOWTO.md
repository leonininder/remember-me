# Runtime how-to — FakeJev vs HttpJev

**Written:** 2026-09-20 (CST / Asia/Taipei)  
**Audience:** developers running remember-me locally. No secrets in this file.

---

## Defaults

| Mode | Network | When |
|------|---------|------|
| **FakeJev** (default) | None | demo, bake-off, CI, pytest |
| **HttpJev** (optional) | TypeSafe System One | only with a real `TYPESAFE_API_KEY` + live pilot (contract fixed; bake-off not yet run) |

CLI always uses FakeJev today:

```bash
pip install -e ".[dev]"
remember-me demo
remember-me bakeoff --out bakeoff_metrics.json
remember-me score-report
```

---

## FakeJev (what actually runs)

```python
from remember_me import FakeJev, MemoryPipeline, TopologyGraph

g = TopologyGraph()
g.observe(node_id="pref_theme", content="User prefers dark theme", tags=["preference"], salience=0.9)
pipe = MemoryPipeline(g, FakeJev(), top_k=5)
result = pipe.run("What is my UI theme preference?")
assert result.jev_called
```

### Behavior

- Deterministic pseudo-confidence from `sha256(query|node_id|model_pin)`.
- Chaos knobs: `force_timeout`, `force_deny`, `force_malformed`, `confidence_override`, `action_override`.
- Always redacts before recording `last_outbound`; tests assert no secrets.
- **Not** TypeSafe. Do not cite FakeJev latency as cloud latency.

### Chaos / fail-closed smoke

```python
from remember_me.jev_client import FakeJev
from remember_me.pipeline import MemoryPipeline
from remember_me.graph import TopologyGraph

g = TopologyGraph()
g.observe(node_id="a", content="x", tags=["t"], salience=0.5)
pipe = MemoryPipeline(g, FakeJev(force_timeout=True), top_k=3)
r = pipe.run("anything")
assert r.fail_closed_count >= 1
assert all(d.fail_closed for d in r.decisions)
```

---

## HttpJev (System One contract — live bake-off still pending)

```python
import os
from remember_me.jev_client import HttpJev
from remember_me.pipeline import MemoryPipeline

# Requires TYPESAFE_API_KEY in the environment. Never commit keys.
client = HttpJev(
    api_key=os.environ.get("TYPESAFE_API_KEY"),
    # default base_url = https://api.typesafe.ai/v1/systemone
    model_pin="jev-1.13.0",
    timeout_s=5.0,
    include_raw_query=False,  # David P1: query_hash only unless True
)
# pipe = MemoryPipeline(graph, client, top_k=5)
```

### Contract (fixed 2026-09-20)

| Item | Value |
|------|-------|
| Endpoint | `POST https://api.typesafe.ai/v1/systemone` |
| Auth | `Authorization: Bearer <TYPESAFE_API_KEY>` |
| Body | `{model, state, questions{id: {type, instructions, criteria?}}}` |
| Response | `{model, answers{id: noul / choice / score}, usage?}` |
| Model pin | `jev-1.13.0` (`JEV_MODEL_PIN`) |

Egress: by default **no raw `query` string** — `state.query_hash` (sha256 hex) always; `query_preview` only if `include_raw_query=True`. Hydrate issues **one System One call per redacted candidate**.

### Remaining blockers before claiming “cloud works”

1. **No live key / pilot in this repo yet** — SCORECARD and bake-off remain FakeJev-only.
2. Need at least one logged successful redacted call (pin + usage) before advertising cloud mode.
3. Optional: chaos against real 401/403/429/timeout once a key exists.

HttpJev **speaks** System One now; treat live mode as **unproven until key + pilot**, not as a broken client.

### Fail-closed behavior (intended)

On missing key, timeout, HTTP 401/403, 4xx/5xx, bad JSON, or missing node:

- `JevBatchResponse` sets `timed_out` / `denied` / `malformed`
- `policy.map_hydrate_action` → **skip** (or optional local stub-only for top-k)

This matches TypeSafe guidance: confidence/probabilities are **not** permission to act; application policy owns thresholds.

---

## Model pin

Package constant: `JEV_MODEL_PIN` → **`jev-1.13.0`** (see `types.py`).

Public aliases: `jev-latest` (stable), `jev-preview`. Prefer the **versioned** ID when calibrating thresholds so alias moves do not silently invalidate floors.

---

## Environment

| Variable | Used by | Notes |
|----------|---------|-------|
| `TYPESAFE_API_KEY` | `HttpJev` only | Never commit; CI leaves empty + FakeJev |
| (none) | FakeJev | Offline |

Do not paste keys into agent prompts. Prefer shell env / secret store.

---

## Makefile shortcuts

```bash
make bakeoff   # offline FakeJev metrics JSON
# (see Makefile for test/lint targets)
```

---

## Sanity checklist before claiming “cloud works”

- [x] HttpJev posts to `/v1/systemone`
- [x] Request uses `state` + typed `questions` (noul/choice/score)
- [x] Response `answers` mapped into `JevBatchResponse` / GateDecision
- [ ] At least one logged successful call with pin + usage tokens (redacted state)
- [ ] Timeout / 401 / malformed chaos against **real** responses
- [ ] Live bake-off JSON committed separately from FakeJev metrics
