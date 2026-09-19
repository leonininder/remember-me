# SCORECARD — remember-me

**Status:** PREVIEW ONLY — NOT A FORMAL SKILL  
**Card / freeze:** PS-REMEMBER-ME-2026-09-19 / freeze-2026-09-19-v1  
**Scored:** 2026-09-19 (CST / Asia/Taipei)  
**Package:** `/workspace/remember-me` v0.1.0 (`remember_me`)  
**Evidence basis:** What was built and verified offline (FakeJev). No live TypeSafe pilot.

---

## Leon dimensions (1–10)

| Dimension | Weight | Score | Notes |
|-----------|-------:|------:|-------|
| Evidence | 20% | **8.0** | Architecture freeze + offline 50-query bake-off JSON; FakeJev only (no live Jev call logs yet) |
| Goal fit | 20% | **9.0** | Clear split: local retrieve → redact → Jev gates → hydrate; Jev ≠ store ≠ ranker |
| Runtime | 15% | **8.0** | Installable package, CLI `remember-me` demo/bakeoff offline; HttpJev present but unproven against real API |
| Verification | 15% | **8.5** | pytest suite + coverage gate, fail-closed + redaction + `jev_called` assertions |
| Safety | 10% | **8.5** | Fail-closed defaults, outbound redaction contract + tests, synthetic fixtures only |
| License | 10% | **9.0** | MIT LICENSE; dependency licenses clean for showcase (pydantic/httpx) |
| Maintainability | 10% | **8.5** | src layout, docs (README/ARCHITECTURE/SECURITY), CI, question-ID registry, model pin |
| **Weighted overall** | 100% | **8.5** | |

### Weighted calculation

```text
0.20×8.0 + 0.20×9.0 + 0.15×8.0 + 0.15×8.5 + 0.10×8.5 + 0.10×9.0 + 0.10×8.5
= 1.60 + 1.80 + 1.20 + 1.275 + 0.85 + 0.90 + 0.85
= 8.475 ≈ 8.5
```

---

## Bake-off snapshot (offline FakeJev)

From `bakeoff_metrics.json` (k=5, n=50):

| Mode | precision@k | recall@k | overshare_rate | p95 latency (ms) | jev_calls |
|------|------------:|---------:|---------------:|-----------------:|----------:|
| hindsight_stub_only | ~0.39 | ~0.98 | 0.04 | ~0.28 | 0 |
| jev_gated | ~0.47 | ~0.97 | 0.04 | ~0.50 | 49 |

Delta precision@k ≈ **+0.085** with negligible overshare change; latency remains sub-ms offline (not a live cloud budget).

---

## Score-improvement actions (toward phase gates ≥9.5)

1. Log **live** Jev hydrate calls (pin `jev-1.13.0`) on personal-prefs only → +Evidence +Runtime  
2. Chaos suite against real timeout/403 responses (not only FakeJev flags) → +Safety +Verification  
3. Independent privacy/adversarial review of redaction allowlist → +Safety  
4. Document “Jev optional vs default” decision with bake-off deltas under live latency budget → +Goal fit  
5. Keep overall ≤9.5 until Phase 2 exit + Leon approval (Pre-Skill rule)

---

## Red-line check (no automatic penalties applied)

| Red line | Status in this build |
|----------|----------------------|
| No PII/secrets egress | Tests assert redacted outbound; fixtures synthetic |
| Fail-closed | Policy + chaos tests (timeout/deny/malformed) |
| No theater (Jev on hydrate path) | Integration asserts `jev_called` / `call_count` |
| Jev not TEMPR replacement | Retriever is local-only |
| No auto-wiki from Jev | Not implemented (non-goal) |

---

## Verdict

**Keep as Pre-Skill / PREVIEW.** Fusion architecture is implemented and verified offline.  
**Do not** promote to formal skill: overall **8.5 ≤ 9.5**, no live Jev pilot, bake-off is FakeJev-only.
