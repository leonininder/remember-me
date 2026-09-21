# Review packet addendum — Audit / Chaos / Allowlist (offline closes)

**For:** David · Justin Sun  
**Date:** 2026-09-21 (CST / Asia/Taipei)  
**Parent packet:** [REVIEW_PACKET.md](REVIEW_PACKET.md)  
**David adversarial correction:** overall **≈8.2** (Evidence **7.5**) — acknowledged in SCORECARD.

---

## What closed offline (this turn)

| # | Blocker | Close evidence |
|---|---------|----------------|
| 1 | Real HTTP chaos (not FakeJev `force_*`) | `tests/test_http_chaos.py` — HttpJev via httpx mock: **401, 403, 429(+Retry-After), timeout, malformed JSON** → `fail_closed` / `deny_emit` / `deny_writeback`; never silent allow. HttpJev maps 429 → `timed_out` with `retry_after=` in error. |
| 2 | Persistent GateAuditRecord | `src/remember_me/audit.py` — append-only **JSONL** or **SQLite**; `record_from_hydrate/emit/writeback/escalation`; tests write+read+redaction. |
| 3 | EscalationRecord denylist leak | **Positive ALLOWLIST** in `escalate_human` (`ESCALATION_SNAPSHOT_ALLOWLIST`). Free-text `proposed_summary` / `email` / novel keys dropped. Emit path fingerprints summaries (`proposed_chars` + `proposed_summary_sha256`) — never egresses body text. |
| 4 | Adversarial redaction | `tests/test_adversarial_redact.py` — fake API keys, emails, long bodies, **tag/node_id side-channels**; hydrate + emit + writeback outbound clean. |
| 5 | FakeJev conf∝local_score | Formally labeled **NON-EVIDENCE** in SCORECARD + `docs/HONEST_LIMITS.md` + `bakeoff.py` docstring. Mode language: **`local_topk_stub`** (not Hindsight product). |
| 6 | CI workflow file | `.github/workflows/ci.yml` present (pytest + ruff, 3.11–3.13). **Do not claim CI green on main until remote green.** |

---

## SCORECARD delta (honest)

| Dimension | Prior intent | After David correction |
|-----------|-------------:|------------------------|
| Evidence | 8.0 | **7.5** (bake-off non-evidence) |
| Verification | 9.0 claimed / David 8.5 | **8.5** (chaos landed offline; remote CI unclaimed) |
| Safety | 8.5 | **9.0** (allowlist + GateAuditRecord + adversarial) |
| Overall | ~8.6 | **~8.2** |

**Still not ≥9.5.** No invented live TypeSafe call logs.

---

## Pytest

Run: `pytest -q` — must be green after this addendum. See SCORECARD for count at freeze.

---

## Suggested reviewer language

`APPROVE_WITH_CONDITIONS` — offline chaos + audit + allowlist land; Evidence cut acknowledged; keep PREVIEW; **REJECT** acceleration / ≥9.5 until live logs + remote CI + Leon sign-off.
