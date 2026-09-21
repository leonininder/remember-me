# SCORECARD — remember-me

**Status:** PREVIEW ONLY — NOT A FORMAL SKILL  
**Card / freeze:** PS-REMEMBER-ME-2026-09-19 / freeze-2026-09-19-v1  
**Scored:** 2026-09-19 (CST / Asia/Taipei); Phase 9.5 dual-gate refresh 2026-09-21; **David adversarial correction 2026-09-21**  
**Package:** `/workspace/remember-me` v0.1.0 (`remember_me`)  
**Evidence basis:** Offline FakeJev + pytest (138 passed). **No live TypeSafe pilot. FakeJev bake-off is NOT product evidence** (conf ∝ local_score).

---

## Leon dimensions (1–10)

| Dimension | Weight | Score | Notes |
|-----------|-------:|------:|-------|
| Evidence | 20% | **7.5** | David correction: FakeJev bake-off labeled non-evidence; no live Jev call logs |
| Goal fit | 20% | **9.0** | Dual egress + escalate_human + no-rerank; Jev ≠ store ≠ ranker |
| Runtime | 15% | **8.0** | CLI dual demo + fan-out defaults; HttpJev still unproven live |
| Verification | 15% | **8.5** | Real HttpJev HTTP chaos (401/403/429/timeout/malformed) + allowlist tests; remote CI on main not yet claimed |
| Safety | 10% | **9.0** | Positive ALLOWLIST EscalationRecord + GateAuditRecord store + adversarial redact |
| License | 10% | **9.0** | MIT; pydantic/httpx clean |
| Maintainability | 10% | **8.0** | src layout + docs + `.github/workflows/ci.yml` present; **do not claim CI green on main until remote green** |
| **Weighted overall** | 100% | **~8.2** | David adversarial ≈8.2; **not ≥9.5** |

### Weighted calculation

```text
0.20×7.5 + 0.20×9.0 + 0.15×8.0 + 0.15×8.5 + 0.10×9.0 + 0.10×9.0 + 0.10×8.0
= 1.50 + 1.80 + 1.20 + 1.275 + 0.90 + 0.90 + 0.80
= 8.375 ≈ 8.2–8.4 (report **~8.2** per David correction)
```

Honesty note: Evidence cut to **7.5** because FakeJev conf∝local_score bake-off must not be read as product proof. Safety up on allowlist + persistent audit. **Do not advertise ≥9.0 overall or ≥9.5.**

---

## Bake-off snapshot (offline FakeJev) — NON-EVIDENCE

From `bakeoff_metrics.json` (k=5, n=50) — regenerate via `make bakeoff`:

| Mode | precision@k | recall@k | overshare_rate | p95 latency (ms) | jev_calls |
|------|------------:|---------:|---------------:|-----------------:|----------:|
| local_topk_stub | ~0.387 | 0.98 | 0.04 | ~0.22 | 0 |
| jev_gated | ~0.472 | 0.97 | 0.04 | ~0.35 | 49 |

**NON-EVIDENCE label:** FakeJev heuristic **correlates with `local_score`**; Δ precision is a wiring/regression signal only — **not** live TypeSafe proof and **not** a Hindsight comparison.

---

## Phase 9.5 offline closes (2026-09-21)

- Dual-gate egress + escalate_human + FANOUT_DEFAULTS + no-rerank
- **HttpJev HTTP chaos** (httpx mock): 401/403/429+Retry-After/timeout/malformed → fail-closed
- **Persistent GateAuditRecord** (JSONL/SQLite) — no secrets/bodies
- **EscalationRecord positive ALLOWLIST** (no proposed_summary free text; hash-only fingerprint)
- Adversarial redaction (keys/emails/long bodies/tag+node_id side-channels)
- Docs: see `docs/REVIEW_PACKET_ADDENDUM_AUDIT_CHAOS.md`

---

## Remaining blockers to honest ≥9.5

1. Live TypeSafe hydrate/emit call logs (pin `jev-1.13.0`)  
2. Remote CI green on main (workflow file exists; do not claim until remote green)  
3. Dual-track bake-off under live RTT (not FakeJev)  
4. Leon formal sign-off  

---

## Verdict

**Keep as Pre-Skill / PREVIEW.** Overall **~8.2** after David adversarial correction.  
**REJECT** ≥9.5 / acceleration / beat-Hindsight narratives on this evidence.

See [docs/REVIEW_PACKET.md](docs/REVIEW_PACKET.md) + [docs/REVIEW_PACKET_ADDENDUM_AUDIT_CHAOS.md](docs/REVIEW_PACKET_ADDENDUM_AUDIT_CHAOS.md).
