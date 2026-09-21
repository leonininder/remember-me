# JustinSun 重評 — offline must-fix closes (addendum)

**Date:** 2026-09-21 22:42 CST (Asia/Taipei)  
**Tree:** `/workspace/remember-me` @ `ec11fa6`  
**Against:** `docs/REVIEW_PACKET_ADDENDUM_AUDIT_CHAOS.md` + prior `JUSTIN_SUN_2026-09-21.md` (8.4)  
**Method:** Read addendum + SCORECARD; `pytest -q` → **138 passed**; spot `test_http_chaos` / `test_adversarial_redact` / `audit.py`; probe `escalate_human` allowlist + `GateAuditStore` JSONL round-trip; `ruff check` → **2× E501** in `jev_client.py` (Retry-After lines).

---

## Verdict

**`APPROVE_WITH_CONDITIONS`** — offline chaos + GateAudit + allowlist + adversarial redact **land**; keep PREVIEW.  
**`REJECT`** ≥9.5 / formal skill / acceleration narrative until live logs + **remote** CI green + Leon sign-off.

**Weighted overall: 8.3** (prior Justin 8.4 → slight Evidence cut; Safety/Verification up offline; ruff red caps Maintainability).

Aligned with David ~8.2 band; I report **8.3** after verifying closes.

---

## Leon 10-pt (re-score)

| Dimension | Weight | Prior | Now | Notes |
|-----------|-------:|------:|----:|-------|
| Evidence | 20% | 8.0 | **7.5** | Bake-off formally NON-EVIDENCE; still zero live logs |
| Goal fit | 20% | 8.8 | **8.8** | Architecture fit intact; refuse SCORECARD 9.0 rubber-stamp on unproven value-half |
| Runtime | 15% | 8.2 | **8.0** | Live HttpJev still unproven — agree SCORECARD cut |
| Verification | 15% | 8.6 | **8.4** | Real httpx-mock 401/403/429/timeout/malformed → fail-closed (good). Cap: **ruff E501 fails locally** while CI runs ruff → remote green not ready |
| Safety | 10% | 8.3 | **8.8** | Positive Escalation allowlist + persistent GateAuditRecord + adversarial suite verified. Not 9.0: no external/independent review; tag fields still rely on assert_no_secrets |
| License | 10% | 9.0 | **9.0** | unchanged |
| Maintainability | 10% | 8.2 | **7.8** | Commit landed (`ec11fa6`); honesty docs stronger; **ruff red + no remote Actions proof** |
| **Weighted** | 100% | 8.4 | **8.3** | |

```text
0.20×7.5 + 0.20×8.8 + 0.15×8.0 + 0.15×8.4 + 0.10×8.8 + 0.10×9.0 + 0.10×7.8
= 1.50 + 1.76 + 1.20 + 1.26 + 0.88 + 0.90 + 0.78
= 8.28 ≈ 8.3
```

---

## Closed vs open

**Closed offline (verified):** HTTP chaos suite; GateAuditRecord JSONL/SQLite; Escalation positive allowlist (probe: `email`/`content`/`proposed_summary` dropped); adversarial redact tests; FakeJev NON-EVIDENCE labeling; `local_topk_stub` rename; `.github/workflows/ci.yml` tracked in git.

**Still open (must-fix to clear 9.5):**
1. Fix ruff E501 (2 lines) so CI can pass  
2. Remote GitHub Actions **green on main** (file ≠ green)  
3. Live TypeSafe hydrate/emit call logs (needs Leon `TYPESAFE_API_KEY`)  
4. Live RTT dual-track bake-off JSON (quality/token/overshare; not FakeJev)  
5. Leon formal sign-off; SCORECARD stay &lt;9.5 until 1–4  

Hard deal-breakers unchanged.

