# Leon formal sign-off — 2026-09-22 (Asia/Taipei)

**Signer:** Leon  
**Time:** 2026-09-22 07:49 CST  
**Repo tip at sign-off intent:** `4fbd874` (main; subsequent docs commit may follow)  
**Choice (verbatim intent):** 簽核 remember-me 目前 PREVIEW／APPROVE_WITH_CONDITIONS 狀態

## What this sign-off accepts

- Package remains **PREVIEW / Pre-Skill**, not a formal shipped skill.
- Reviewer posture: **APPROVE_WITH_CONDITIONS** (David ≈8.8, Justin ≈8.6 after remote CI).
- Live enrich v2 quality bars: **PROMOTE_CANDIDATE** on `personal_prefs` only.
- Known limits remain in force:
  - **No ≥9.5** claim
  - **No acceleration** marketing (live latency ≫ local baseline)
  - Ontology / fixture tilt risk acknowledged
  - Independent human redact / allowlist review **still open**

## What this sign-off does **not** do

- Does not promote to ≥9.5
- Does not close independent redact/allowlist human review
- Does not authorize raw `query_preview` as default egress
- Does not lower T_ACCEPT / T_ESCALATE into noise

## References

- SCORECARD.md (author ~8.8)
- docs/reviews/LIVE_PILOT_ENRICH_V2_2026-09-22.md
- docs/reviews/DAVID_2026-09-22_REMOTE_CI.md
- docs/reviews/JUSTIN_SUN_2026-09-22_CI_GREEN.md
- Actions: https://github.com/leonininder/remember-me/actions/runs/35668516213
