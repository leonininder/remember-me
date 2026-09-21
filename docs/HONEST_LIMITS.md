# Honest limits — remember-me

**Written:** 2026-09-20 (CST / Asia/Taipei)  
**Scope:** What is REAL vs FAKE vs CLAIMED. Do **not** paste unverified acceleration claims to GitHub.

---

## One-line verdict

Offline FakeJev bake-off shows a **synthetic gate** can filter candidates and nudge precision@k. That is **not** evidence that live TypeSafe Jev accelerates memory recall, reduces tokens, or beats Hindsight under production latency.

---


## FakeJev bake-off = NON-EVIDENCE (David 2026-09-21)

FakeJev confidence is **heuristically correlated with `local_score`** (`≈ 0.45 + 0.5×local_score + noise`).
Therefore:

- Precision@k deltas from `local_topk_stub` vs `jev_gated` are **wiring / regression signals only**.
- Do **not** cite bake-off JSON as product-market proof, live TypeSafe proof, or a Hindsight win.
- Baseline mode string is **`local_topk_stub`** — not the commercial Hindsight product.


## REAL (implemented + verified offline)

| Item | Evidence |
|------|----------|
| Local topology graph + markers | `src/remember_me/graph.py`, fixtures |
| TEMPR-style **local** retrieve (keyword/tag/recency) | `retrieve.py` — Jev never ranks |
| Redaction contract (bodies/secrets off outbound) | `redact.py` + tests |
| Pipeline: retrieve → redact → gate → hydrate | `pipeline.py`; orphans forbidden |
| Fail-closed policy thresholds | `policy.py` (0.85 / 0.55); chaos flags on FakeJev |
| Offline FakeJev bake-off (n=50, k=5) | `bakeoff.py` → `bakeoff_metrics.json` |
| Installable package + CLI | `remember-me demo` / `bakeoff` / `score-report` |
| SCORECARD PREVIEW ~8.5 | `SCORECARD.md` (2026-09-19) |
| Architecture intent documented | `ARCHITECTURE.md`, README Limitations |

### Offline bake-off numbers (FakeJev only)

From `bakeoff_metrics.json` (do not re-label as live):

| Mode | precision@k | recall@k | overshare_rate | p95 latency (ms) | jev_calls |
|------|------------:|---------:|---------------:|-----------------:|----------:|
| local_topk_stub | ~0.387 | 0.98 | 0.04 | ~0.22 | 0 |
| jev_gated | ~0.472 | 0.97 | 0.04 | ~0.35 | 49 |

Delta precision@k ≈ **+0.085**. Latency is **sub-millisecond local CPU**, not cloud RTT.

---

## FAKE / SIMULATED (must be labeled as such)

| Item | Reality |
|------|---------|
| **FakeJev** | Deterministic hash of `query\|node_id\|model_pin` → confidence/action. **No network. Not calibrated. Not TypeSafe.** |
| Bake-off “Jev-gated” wins | FakeJev’s heuristic correlates with `local_score`; precision lift can be an artifact of that correlation |
| “Hindsight” / local baseline | Mode string `local_topk_stub` — local top-k stubs only; **not** the commercial Hindsight product under live load |
| Demo GIF / assets | Placeholder only (`assets/README.md`) |
| CI “Jev on path” | Proves FakeJev was invoked (`jev_called`), not that cloud Jev judged well |

---

## CLAIMED / INTENDED but unproven

| Claim | Status |
|-------|--------|
| Live TypeSafe Jev improves hydrate quality | **Unknown** — no live call logs in repo |
| Jev accelerates memory (latency) | **Must not claim** — live Jev is typically ~70–500 ms (vendor/public writeups); offline bake-off cannot falsify this |
| HttpJev works against production API | **Contract fixed** (System One); **live still unproven** — no key/pilot logs yet |
| Drop-in Claude / Codex / Hermes skill | **Not true today** — library + CLI only; no shipped agent skill/hooks package |
| Replaces Mem0 / full memory OS | Explicit non-goal |
| Community Jev = memory hydrate gate | Community mainly uses Jev for **context compaction / routing / triage**, not topology memory stores (see `INTEGRATION_MATRIX.md`) |

### HttpJev contract status (fixed 2026-09-20)

remember-me `HttpJev` now matches public System One:

- URL: `POST https://api.typesafe.ai/v1/systemone`
- Body: `{model, state, questions}` → parses `{answers, model, usage?}`
- Pin: `jev-1.13.0` (`JEV_MODEL_PIN`)
- Egress: `query_hash` by default; no top-level `query`; raw preview opt-in
- Hydrate: **batched multi-candidate** single POST when possible (`state.candidates` + `{node_id}__…` question keys); admit stays single-call

**Live bake-off still not run** — needs `TYPESAFE_API_KEY` + redacted pilot log. Until then, do **not** claim cloud hydrate quality or latency wins. Contract gap is closed; integration proof is not.

---

## Community reality check (Jev ≠ memory DB)

What people actually ship with Jev (public sources):

1. **Typed decisions** — Choice / Score / Noul; cannot speak/generate prose ([Flavio Copes deep dive](https://flaviocopes.com/jev/), [TypeSafe agent skill](https://docs.typesafe.ai/agent-skill)).
2. **Confidence floors in application code** — e.g. review ~0.5, destructive ~0.9 are **examples**, not model defaults.
3. **Pin model versions** when calibrating thresholds (`jev-1.13.0` in responses).
4. **Compaction** — keep/drop stale **tool results** (fast-jev-compaction, hermes-jev-compact, LiteLLM jev-compaction), **not** ranking a personal knowledge graph.
5. **Official skill** teaches System One API usage — not remember-me hydrate topology.

remember-me’s intended niche (post-recall hydrate admit/skip) is **architecturally compatible** with System One, but **not what the compaction community is measuring**.

---

## What must NOT be claimed on GitHub

1. “Jev accelerates memory” / “faster than Hindsight” without a **live** bake-off JSON + call logs.
2. Live p50/p95 latency numbers derived from FakeJev.
3. “Official Claude/Codex/Hermes skill for remember-me” (none exists yet).
4. Compatibility with TypeSafe API without proving a successful live response (contract is fixed; live log still required).
5. Star counts, Fortune 500, or production case studies that do not exist.
6. That FakeJev precision@k deltas generalize to live calibrated Jev.

---

## What works today / what does not

### Works today

- Offline demo + bake-off + pytest suite
- Local retrieve + redact + FakeJev gate + hydrate
- Fail-closed mapping for simulated timeout/deny/malformed
- Documentation honesty at PREVIEW / Pre-Skill

### Does not work today (or unproven)

- Live HttpJev end-to-end against TypeSafe (client speaks System One; key + pilot missing)
- Proven live latency / token / quality win vs Hindsight or dump-all
- Drop-in agent skill for Claude Code / Codex / Hermes
- Mac wiki cross-check from this research box (ListMachines / wiki path unavailable here)

### Unknown (mark unknown, do not invent)

- Live Jev hydrate decision quality on personal-prefs markers
- Fail-closed rate under real 401/403/429/529
- Token savings when hydrate stubs replace full bodies under live policy
- Whether community compaction thresholds transfer to memory hydrate questions

---

## Related docs

- `docs/COOKBOOK.md` — Playground + hydrate cookbook
- `docs/MISCONCEPTIONS.md` — common mistakes
- `docs/GETTING_STARTED_ZH.md` — 繁中快速上手
- `docs/RUNTIME_HOWTO.md` — FakeJev vs HttpJev
- `docs/INTEGRATION_MATRIX.md` — Claude / Codex / Hermes
- `docs/BAKEOFF_PLAN.md` — minimal live falsification plan
- `docs/README_LIMITATIONS_DRAFT.md` — draft README merge text


---

## LIVE pilot 2026-09-22 (HttpJev) — honest

**REAL:** System One hydrate/emit succeed after Choice `criteria`→dict and Score `criteria`→ordered string levels. Smoke + 50-query live bake-off logs under `docs/reviews/` and `bakeoff_metrics_live.json`. Model pin `jev-1.13.0` echoed; usage tokens recorded; fail_closed_rate 0.0 (no 429 this run).

**NOT proven:** “Jev accelerates memory.” Live arm C vs B: p95 latency **+~509 ms**, precision@k **−0.387** (near-total `skip` under 0.85/0.55 bands with hash-only state). That **falsifies** acceleration on this fixture/threshold setup.

**Still FAKE / NON-EVIDENCE:** Offline FakeJev `bakeoff_metrics.json` numbers.

**Do not claim:** ≥9.5 overall, beat-Hindsight, or remote Actions green without proof.
