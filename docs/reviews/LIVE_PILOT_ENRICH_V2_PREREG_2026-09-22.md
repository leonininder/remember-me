# LIVE pilot enrich v2 — pre-registered bars (before bake-off)

**When:** 2026-09-22 (Asia/Taipei)  
**Tree base:** `05782a3` + enrich v2 allowlist signals  
**Constraints:** `include_raw_query=False`; ALLOWED_OUTBOUND_KEYS only; **no** lowering `T_ACCEPT`/`T_ESCALATE` into conf≈0.2–0.5 noise; no ≥9.5 / acceleration claim.

---

## Why v1 precision stalled (~0.174)

Sample LIVE smoke (enrich v1): gold nodes often `skip` at conf≈0.4 while off-gold UI stubs admitted at conf≈0.6–0.8. Drivers:

1. **Coarse intent** — e.g. “What UI language…?” → `preference_ui` (needle `ui`) instead of locale.
2. **Weak discrimination** — `stub_tags` + `intent_class` alone do not separate theme vs font vs editor among same-family candidates.
3. **Conf mass** — mean≈0.59, max≈0.82: almost no accept-band (≥0.85); mid-band admits stubs, often the wrong ones.

---

## Enrich v2 allowlisted signals (structured only)

| Key | Level | Notes |
|-----|-------|-------|
| `intent_class` | state | Fixed routing (locale before bare ui; soft-negate “without health”) |
| `intent_focus` | state | Finer closed enum: theme/font/language/drink/… |
| `length_bucket` | state | short/medium/long |
| `stub_tags` | candidate | ≤8 capped tags |
| `topic_family` | candidate | Closed family from local tag ontology |
| `overlap_tag_count` | candidate | \|tags ∩ intent ontology\| (0..8) |
| `intent_topic_fit` | candidate | strong_match / weak_match / mismatch / unknown |
| `candidate_rank_in_topk` | candidate | 1-based local retrieve rank |
| `salience_bucket` | candidate | low/mid/high (from local salience; raw salience not required outbound) |
| `stub_token_bucket` | candidate | tiny/small/medium/large from tokens_est |

No `query_preview` / free-text query egress.

---

## Pre-registered bars (evaluate AFTER live bake-off)

| Bar | Pass condition |
|-----|----------------|
| Precision | C `precision_at_k` ≥ B − 0.05 (≈0.337 when B≈0.387) |
| Overshare | C `overshare_rate` ≤ 0.02 **and** ≤ B |
| Fail-closed | C `fail_closed_rate` ≤ 0.05 |
| Escalate | **report** `escalate_rate` (no hard gate) |
| Promotion | `NON_PROMOTE` until precision + overshare + fail_closed pass |
| Marketing | no ≥9.5 SCORECARD claim; no acceleration claim |

---

## Held-out threshold policy

- Split fixtures ~30 calibrate / 20 holdout (query id order).
- Tune `T_*` **only if** live (or calibrate) conf for **gold** candidates shows separable mass **above 0.55** (and ideally peaks toward accept), not by lowering floors into 0.2–0.5 noise.
- Default for this bake-off: **keep 0.85 / 0.55**.

---

## Stop condition

One serious enrich pass + one live bake-off. If still below bar, stop and report the smallest additional allowlisted field needed — do not infinite-loop API spend.
