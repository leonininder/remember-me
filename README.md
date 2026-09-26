# remember-me

**Agents forget. Remember Me decides what to hydrate.**

Local candidates first. TypeSafe **Jev** never ranks — Jev only admits. A **decision gate**, not a memory bank or chat LLM.

**Surfaces:** [Library](#quick-start) · [CLI](#30-second-demo) · [Cookbook](docs/COOKBOOK.md) · [ZH 繁中](docs/GETTING_STARTED_ZH.md) · [Bake-off](#bake-off) · [Launch checklist](docs/LAUNCH_CHECKLIST.md)

### System One / Built with TypeSafe Jev

**Decision gate showcase, not a chat LLM.** Jev (System One) answers typed Choice / Score / Noul only — it **cannot generate prose**. remember-me uses it **after** local recall to decide hydrate / stub / skip / promote on a **redacted** candidate set. See the [Cookbook](docs/COOKBOOK.md). Do **not** treat FakeJev offline demos as live TypeSafe proof.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: PREVIEW](https://img.shields.io/badge/status-PREVIEW%20Pre--Skill-orange.svg)](SCORECARD.md)

**中文快速上手：** [docs/GETTING_STARTED_ZH.md](docs/GETTING_STARTED_ZH.md)

---

## 30-second demo

```bash
pip install -e ".[dev]"   # from repo root (Python 3.11+)
remember-me demo
```

Offline by default (`FakeJev`). Optional:

```bash
remember-me bakeoff
remember-me demo-dual
remember-me score-report
```

`HttpJev` speaks System One (`POST /v1/systemone`, pin `jev-1.13.0`) and can **batch** multi-candidate hydrate into one POST — live mode still needs a key + pilot log; do **not** treat cloud as proven.

### Screenshot / GIF

**Hero media not shipped.** There is no `assets/demo.gif` in this tree (do not link a missing file — that would 404).

| Asset | Status |
|-------|--------|
| Capture instructions | [`assets/README.md`](assets/README.md) — **TODO:** record `demo.gif` (asciinema/ffmpeg) before linking it from this README |
| Fallback until then | Terminal output of `remember-me demo` + Mermaid architecture below |

Do not invent GIF bytes or placeholder media.

---

## Why not just dump context?

| Approach | What it does | What it doesn't |
|----------|--------------|-----------------|
| **Dump everything** | Shoves markers into the LLM | Budget, privacy, precision |
| **Plain TEMPR / local top-k** | Keyword / tag / recency recall | Calibrated hydrate / skip / promote |
| **Local top-k stub** (bake-off baseline) | Keyword/tag top-k stubs only | Commercial Hindsight product; calibrated live memory OS |
| **Mem0 / full memory banks** | Store + retrieve product surface | Separating *rank* from *admit* |
| **remember-me** | **Decision gate** after local recall | Replace your store or embedder |

Honest pitch: we sit **between** local candidates and the LLM. Jev is **not** the database and **not** the similarity ranker.

---

## Features

| Feature | Detail |
|---------|--------|
| Local topology graph | Markers + `content_ref` (bodies stay off outbound) |
| TEMPR-style recall | Keyword / tag / recency — **no Jev ranking** |
| Hydrate gate | Choice `hydrate_action` + Score need + Noul still_matters |
| Admit gate | Choice admit + closed node-kind taxonomy |
| Egress / writeback gate | `decide_emit` / `decide_writeback`; fail-closed deny |
| Escalate human | First-class mid-band + conflicts; structured EscalationRecord |
| Fail-closed policy | timeout / deny / malformed → skip (optional local stub) |
| Redaction contract | Outbound = metadata only; secrets asserted in tests |
| Offline bake-off | 50 synthetic queries → precision / overshare / latency |

---

## Architecture

```mermaid
flowchart LR
  O[Observe / graph store] --> R[LocalCandidateRetriever<br/>TEMPR mock]
  R --> X[Redact markers]
  X --> J[TypeSafe Jev gates<br/>hydrate / admit]
  J --> P[Policy thresholds]
  P --> H[Hydrated nodes → LLM]
```

```text
observe → write markers + content_ref
       → local retrieve candidates     [NO Jev ranking]
       → redact → {node_id, kind, tags, degree, last_touch, local_score, tokens_est}
       → Jev batch: hydrate_action + need + still_matters
       → policy → hydrate winners into LLM context
```

### Policy defaults (fail-closed)

| Confidence | Action |
|------------|--------|
| ≥ 0.85 | `hydrate_full` (or promote) |
| 0.55–0.85 | **`escalate_human`** (+ EscalationRecord) |
| < 0.55 | `skip` |
| timeout / deny / malformed | **fail-closed** → skip |

---

## Quick start

```python
from remember_me import FakeJev, MemoryPipeline, TopologyGraph, NodeKind

g = TopologyGraph()
g.observe(
    node_id="pref_theme",
    content="User prefers dark theme",
    tags=["preference", "ui"],
    salience=0.9,
)

pipe = MemoryPipeline(g, FakeJev(), top_k=5)
result = pipe.run("What is my UI theme preference?")

assert result.jev_called  # Jev is on the hydrate critical path
for node in result.hydrated:
    print(node.node_id, node.action, node.content[:60])
```

Contributor hook: wire the gate with a short cookbook recipe — see [docs/COOKBOOK.md](docs/COOKBOOK.md) and [docs/INTEGRATION_MATRIX.md](docs/INTEGRATION_MATRIX.md) (integrate-style path in ~10 lines of pipeline construction, not a drop-in Claude plugin).

---

## Package layout

```text
src/remember_me/
  types.py       # Marker schema, horizons, closed Choice taxonomies
  graph.py       # In-memory + optional SQLite topology store
  retrieve.py    # LocalCandidateRetriever (not Jev)
  redact.py      # Outbound redaction + secret assertions
  jev_client.py  # FakeJev + HttpJev
  policy.py      # Thresholds + fail-closed mapping
  gates.py       # MemoryGate, EmitEgressGate, WritebackGate, RetainAdmitGate
  fanout.py      # FANOUT_DEFAULTS (frozen question fan-out)
  pipeline.py    # observe → retrieve → redact → jev → hydrate (+ run_egress)
  bakeoff.py     # 50-query offline bake-off → metrics JSON
  cli.py
```

---

## FAQ (fear / honesty)

<details>
<summary>Does it auto-hydrate secrets into the LLM?</summary>

No. Bodies stay behind `content_ref`. Only **redacted marker metadata** is considered for outbound Jev state; hydrate winners are selected by policy after the gate. See [SECURITY.md](SECURITY.md).
</details>

<details>
<summary>Does Jev see message bodies or PII?</summary>

Outbound candidate fields are exactly: `node_id`, `kind`, `tags`, `degree`, `last_touch`, `local_score`, `tokens_est`. Tests assert secrets / bodies never appear in outbound state. Details: [SECURITY.md](SECURITY.md).
</details>

<details>
<summary>Does this need root, Xposed, or hooks?</summary>

No. remember-me is a local Python library + CLI. It does not touch chat apps, accessibility services, or device privileges. (That class of fear FAQ belongs to consumer overlays like Jarvis — not this repo.)
</details>

<details>
<summary>Is FakeJev / bake-off live TypeSafe proof?</summary>

No. Offline FakeJev metrics are **not** live cloud latency or calibrated decision quality. See [docs/HONEST_LIMITS.md](docs/HONEST_LIMITS.md).
</details>

---

## Safety

- Outbound Jev payloads contain **only** redacted marker metadata
- Tests assert secrets / bodies never appear in outbound state
- Fail-closed on Jev errors — no theater wrappers that skip Jev on the hydrate path
- Fixtures under `fixtures/personal_prefs/` are **synthetic** (no PII)

See [SECURITY.md](SECURITY.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Limitations (honest)

- **PREVIEW / Pre-Skill** — not a formal promoted skill. See [SCORECARD.md](SCORECARD.md) (~8.6 weighted after Phase 9.5 offline dual-gate; FakeJev evidence basis — still &lt;9.5).
- **Offline bake-off ≠ live proof.** `remember-me bakeoff` uses **FakeJev** (deterministic, no network). Published `bakeoff_metrics.json` must not be read as TypeSafe cloud latency or calibrated decision quality. See [docs/HONEST_LIMITS.md](docs/HONEST_LIMITS.md) and [docs/BAKEOFF_PLAN.md](docs/BAKEOFF_PLAN.md).
- **No live acceleration claim.** We do **not** claim that Jev accelerates memory versus Hindsight or dump-all. Offline FakeJev precision deltas are **not** live proof. Any future win must be quality/token efficiency under measured live RTT — not “faster FakeJev.”
- **HttpJev contract fixed; live unproven.** Speaks public System One (`POST /v1/systemone`, `state` + typed `questions`; batched multi-candidate hydrate when possible). Do **not** advertise cloud mode as working without a successful redacted call log. See [docs/RUNTIME_HOWTO.md](docs/RUNTIME_HOWTO.md).
- **Gate layer, not a memory OS.** Non-goal: Mem0 / embedder / TEMPR-ranker replacement. Jev must not re-rank local candidates.
- **Not a drop-in Claude / Codex / Hermes skill or plugin.** Library + CLI only; no official TypeSafe skill package. See [docs/INTEGRATION_MATRIX.md](docs/INTEGRATION_MATRIX.md).
- **No theater metrics.** No fake star counts, Fortune 500 logos, or invented production case studies. **FakeJev ≠ product proof.**

---

## Bake-off

Offline harness: **`local_topk_stub`** (local top-k stubs; *not* commercial Hindsight) vs **Jev-gated** (FakeJev) on 50 labeled synthetic queries — precision@k, recall@k, overshare proxy, latency, Jev call count.

```bash
make bakeoff
```

Regenerate committed metrics with `make bakeoff` if numbers drift. See [docs/BAKEOFF_PLAN.md](docs/BAKEOFF_PLAN.md). Do **not** paste bake-off numbers as live product claims.

---

## Community

GitHub **Discussions** are not enabled on this repo (as of 2026-09-26). Prefer **[Issues](https://github.com/leonininder/remember-me/issues)** for bugs, ideas, and adapter / integration questions. Optional Discord / 公众号: only when Leon publishes a real funnel — do not invent QR codes.

**Version signal:** No GitHub Release yet; the **PREVIEW** badge above is the version signal (do not invent a hollow Release or fake changelog).

Repository topics (applied on GitHub; also listed in [CONTRIBUTING.md](CONTRIBUTING.md)):

`python` · `memory-gate` · `typesafe` · `jev` · `system-one` · `agent-memory` · `redaction` · `fail-closed` · `decision-gate` · `llm-agents`

Launch / distribution shell: [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md) (Jarvis → Leon mapping).

---

## Further docs

- [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md) — Jarvis-style distribution checklist
- [docs/DUAL_GATE.md](docs/DUAL_GATE.md) — dual-gate egress + escalate_human
- [docs/REVIEW_PACKET.md](docs/REVIEW_PACKET.md) — David + Justin Sun review packet
- [docs/COOKBOOK.md](docs/COOKBOOK.md) — Playground + System One hydrate cookbook
- [docs/MISCONCEPTIONS.md](docs/MISCONCEPTIONS.md) — common mistakes
- [docs/GETTING_STARTED_ZH.md](docs/GETTING_STARTED_ZH.md) — 繁中快速上手
- [docs/HONEST_LIMITS.md](docs/HONEST_LIMITS.md) — REAL / FAKE / CLAIMED
- [docs/RUNTIME_HOWTO.md](docs/RUNTIME_HOWTO.md) — run offline; HttpJev caveats
- [docs/INTEGRATION_MATRIX.md](docs/INTEGRATION_MATRIX.md) — Claude / Codex / Hermes positioning
- [docs/BAKEOFF_PLAN.md](docs/BAKEOFF_PLAN.md) — live bake-off plan (when ready)
- [docs/reviews/](docs/reviews/) — external review notes
- [ARCHITECTURE.md](ARCHITECTURE.md) · [SECURITY.md](SECURITY.md) · [SCORECARD.md](SCORECARD.md)

---

## License

MIT — see [LICENSE](LICENSE).
