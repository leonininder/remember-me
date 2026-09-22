# Phase C exit — independent human redact review checklist

**Status:** OPEN — awaiting independent human pass (do not treat code CI green as Phase C closed).  
**Allowlists under review:**

- `remember_me.tfl.redact.RECONCILE_STATE_ALLOWLIST`
- `remember_me.tfl.redact.ESCALATION_SNAPSHOT_ALLOWLIST`

**PLAN refs:** §4.7, §6 Phase C exit criterion.

---

## Reviewer instructions

1. Read both frozensets in `src/remember_me/tfl/redact.py` (not only this checklist).
2. Confirm **positive allowlist** posture (no denylist-as-SoT).
3. Confirm forbidden-by-default class is excluded: raw diary, full transcripts, secrets, emails, phone, exact street.
4. Skim adversarial tests in `tests/tfl/test_reconcile_redact.py` — they must stay green, but human judgment is separate.
5. Sign below with name + date + PASS/FAIL + residual risks. **Do not** invent Leon / David / Justin signatures here.

---

## Checklist

| # | Item | Pass? |
|---|------|-------|
| 1 | Reconcile outbound fields ⊆ named allowlist only (`fact_key`, clipped `value_struct`, `valid_from`, `receive_ts`, `salience_tier`, `confidence`, `stub_hash`, `conflict_keys`) | ☐ |
| 2 | Escalation snapshot = reconcile fields + `source_event_id` / `extract_method` / `quarantine_reason` (and documented extras only) | ☐ |
| 3 | No path for diary / body / prose / notes / email / phone / street as active belief value or outbound key | ☐ |
| 4 | `clip_value_struct` + caps still fail closed (stub_hash fallback) under adversarial keys | ☐ |
| 5 | HttpJev reconcile chaos path never APPLY on 401/429/timeout/malformed | ☐ |
| 6 | Quarantine drain never md-appends; never drops on escalate | ☐ |
| 7 | Residual risk notes recorded (below) | ☐ |

---

## Residual risks / notes

_To be filled by human reviewer._

---

## Sign-off (human only)

| Role | Name | Date (Asia/Taipei) | Verdict |
|------|------|--------------------|---------|
| Independent redact reviewer | | | PASS / FAIL |
| Optional second reader | | | |

**Leon product sign-off is out of scope for this checklist.** Phase C exit = redact allowlist review only.
