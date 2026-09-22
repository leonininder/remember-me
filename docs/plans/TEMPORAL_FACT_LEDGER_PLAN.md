# PLAN — Temporal Fact Ledger (TFL) + Jev reconciliation

**Status:** DRAFT for David / Justin Sun review toward **≥9.5 on this PLAN** (not a claim that the product is already ≥9.5)  
**Owner:** Leon (via 小助手)  
**Repo tip context:** remember-me PREVIEW / AWC (~8.6–8.8) after enrich v2 + remote CI; Leon signed PREVIEW/AWC 2026-09-22  
**Codename:** Temporal Fact Ledger (TFL) — working title; supersedes “append-only memory.md” as the memory hygiene path  
**Rule:** Iterate this PLAN until both reviewers score it **≥9.5/10** or explicitly list remaining PLAN gaps; do not stop on implementation until the PLAN clears.

---

## 0. One-sentence mission

Build an open, local-first **temporal fact ledger** that uses TypeSafe **Jev** only as a **fast reconciliation / forget / upsert gate** (never as a chat memory dump), so agent memory stays **small, current, and decidable** as time passes — contributing a reusable pattern for human–AI systems that must update beliefs, not just accumulate text.

---

## 1. Problem (Leon’s failure mode)

Classic agent memory artifacts (`AGENTS.md`, `MEMORY.md`, `SOUL.md`, skill dumps, session transcripts) share a structural flaw:

1. **Append-only growth** — every observation becomes another paragraph.  
2. **Contradiction without resolution** — “today sunny” then “today rainy” both remain; the model must *reason* through conflict at inference time (slow, flaky, token-heavy).  
3. **No childhood→adult rewrite** — early “insects are fun to play with” never yields to “some insects are toxic”; salience never decays; the agent becomes *less* decisive as history lengthens.  
4. **Lost-in-the-middle** — stuffing more context does not fix belief hygiene; it taxes attention and bills.

This is not “need a bigger window.” It is **missing a belief-update engine**.

---

## 2. Deep synthesis of the videos Leon watched

### 2.1 Jev speed demos (e.g. `T4zKauxr7Ug`)

- **What looks fast:** Jev **replacing LLM generation** on closed decisions (route, classify, score) via parallel probability over typed options; side-by-side vs DeepSeek on puzzles / 1k emails / bulk tags.  
- **What is NOT proven:** that adding Jev **after** a fast local retrieve “accelerates memory.” remember-me live enrich v2 already **falsified** that claim (quality ↑, latency ≫ baseline).  
- **Takeaway for TFL:** use Jev where it is honestly fast — **duplicate / same-topic / supersession / TTL / contradiction class** on **structured fact pairs**, with full enough redacted state — not as a hydrate-speed story.

### 2.2 Supermemory (`SHRkOI0yO4Q`)

- Memory ≠ RAG; facts change; later facts should **override** with timeline.  
- **Active forgetting** (TTL) and **user profile** (static + dynamic, injected at session start).  
- Eval honesty: vendor leaderboards are configuration-sensitive; **measure on your own history**.  
- Three questions to grade any memory system: **update? forget? proactive supply?**  
- **Takeaway:** TFL adopts update/forget/proactive profile as **first-class**; does **not** fork Supermemory as the product — we need a **Jev-native reconciliation gate** + local ledger that fits Leon’s redaction / fail-closed culture.

### 2.3 Gary Chen / System One gate framing (`2mtn-Qp59y4` lineage)

- Dual-gate: ingress hydrate + egress admit/writeback; escalate_human; “local candidates first; Jev never ranks; Jev only admits.”  
- **Takeaway:** TFL write path is another **admit gate** — admit a *fact mutation* (upsert / expire / tombstone), not admit prose into the prompt dump.

### 2.4 Critique videos (e.g. 抡锤者)

- Do not bolt Jev into chat workflows as theater (“脱裤子放屁”).  
- **Takeaway:** TFL must show **measurable memory hygiene** (contradiction rate ↓, ledger size stable, decision latency ↓) — not skill-install cosplay.

---

## 3. Design principles (non-negotiable)

1. **Beliefs are versioned facts, not transcripts.** Store `FactKey` + `FactVersion` with `valid_from` / `valid_to` / `superseded_by`.  
2. **Jev decides mutation class; code applies it.** No free-text “memory rewrite” from an LLM as source of truth.  
3. **Fail-closed on write.** If Jev denied / timed out / malformed → **no** silent append; escalate or quarantine. (Chat UX may fail-open elsewhere; the ledger must not.)  
4. **Redaction-first state.** Reconciliation state is structured fields + short stubs + hashes; no dump of full diaries by default (`include_raw_query=False` unless Leon risk-accepts).  
5. **Forget is a feature.** TTL, topic replace, and explicit tombstones are success metrics, not bugs.  
6. **Do not claim “Jev accelerates memory retrieval.”** Claim: **Jev accelerates belief reconciliation vs LLM arbitration** and **keeps context small**.  
7. **Human contribution:** publish an open **Temporal Fact Ledger protocol** (schema + gate question set + eval harness) others can implement — not only a private Leon wiki dump.

---

## 4. Architecture

```text
Event (chat turn / tool result / file / sensor)
    → CandidateFactExtractor (deterministic + optional LLM extract; output = structured CandidateFact only)
    → TopicIndex.lookup(same FactKey / embedding-neighbor keys)  [local, not Jev]
    → JevReconcileGate(state={new, incumbents_redacted}, questions=…)
    → Policy → APPLY: upsert | supersede | merge | expire | tombstone | escalate_human
    → Ledger (SQLite/JSONL) + Audit (GateAuditRecord)
    → ProfileCompiler (static + dynamic slices) for session inject / remember-me hydrate candidates
```

### 4.1 Relation to existing remember-me

| Layer | remember-me today | TFL adds |
|-------|-------------------|----------|
| Retrieve | topology / local top-k | FactKey index + temporal as-of query |
| Gate | hydrate / emit / writeback | **reconcile / forget / supersede** |
| Store | markers + content_ref | **versioned fact ledger** |
| Profile | implicit via tags | **compiled static/dynamic profile** |

TFL is the **write-side belief engine**; remember-me hydrate remains the **read-side admit gate**. Same redaction + audit culture.

### 4.2 Data model (v0)

```text
FactKey:      stable id (e.g. hash(entity + attribute))  # "user.weather.today", "user.attitude.insects"
FactVersion:  { version_id, fact_key, value_struct, valid_from, valid_to?,
                source_event_id, confidence, salience, ttl_hint?,
                status: active|superseded|expired|tombstoned }
ReconEvent:   { ts, new_candidate, incumbent_ids, jev_answers, action, audit_id }
```

**Weather example:**  
- Day1: `weather.local = sunny` valid_from=D1  
- Day2: Jev says `supersedes` same FactKey → Day1 `valid_to=D2`, Day2 active  
- Ask “what’s the weather belief *as of now*?” → one row, no dual messages for the LLM to argue.

**Insects example:**  
- Child: `insects.play = attractive`  
- Adult event: Jev `contradicts` + `salience_shift` → supersede with `insects.safety = caution_toxic_species`; old version retained for timeline but **not** injected into default profile.

### 4.3 Jev question pack (reconcile) — draft

All Choice criteria = **dict** `{key: description}`; Score = ordered **string** levels; pin `jev-1.13.0`.

| Question id | Type | Purpose |
|-------------|------|---------|
| `relation` | Choice | `same_fact` \| `supersedes` \| `contradicts` \| `side_thread` \| `noise` \| `other` |
| `should_forget_incumbent` | Noul | Incumbent should leave active set |
| `ttl_urgency` | Score | How soon this belief should expire (levels: permanent → hours) |
| `profile_worthiness` | Noul | Belongs in static/dynamic profile inject |
| `needs_human` | Noul | Sensitive / identity / medical / legal → escalate |

Policy defaults: T_accept=0.85 / T_escal=0.55 (held unless held-out live conf shows separable bands — **never** lower into noise).

---

## 5. Falsifiable success metrics (pre-register before build)

**Corpus:** synthetic temporal suites (weather flips, address moves, preference reversals, childhood→adult safety) + Leon opt-in redacted personal_prefs lineage.

| Metric | Pass bar (v0) | Falsify if |
|--------|---------------|------------|
| Active ledger size @ N events | ≤ O(unique FactKeys) not O(N) | Grows ~linear with events |
| Contradiction visible to prompt | 0 dual-active same FactKey | ≥1% queries see dual-active conflict |
| Reconciliation decision latency | Jev path p95 report; must beat **LLM-as-judge** arbitration p95 on same pairs | Slower than LLM judge with no quality gain |
| Wrong supersession rate | ≤ 2% on labeled suite | >5% |
| Fail-closed on gate errors | 100% no apply | Any apply on deny/timeout |
| Profile token budget | ≤ ~1–2k tokens typical | Unbounded dump returns |

**Explicit non-metric:** “faster than local retrieve without Jev” — out of scope / previously falsified for hydrate.

---

## 6. Phased delivery

### Phase A — PLAN lock (≥9.5 from David + Justin on *this document*)

- Address all REJECT comments; revise PLAN in-repo; no large code until PLAN ≥9.5 **or** Leon waives in writing.

### Phase B — Ledger + deterministic tests

- SQLite/JSONL FactVersion store; as-of query; supersede/expire APIs; property tests (no dual-active).

### Phase C — JevReconcileGate

- HttpJev + FakeJev; chaos fail-closed; adversarial redact on reconcile state; live smoke logs.

### Phase D — Eval harness `memorybench_tfl`

- Open fixture pack + scripts; publish results as EVIDENCE / NON-EVIDENCE labeled honestly.

### Phase E — ProfileCompiler + remember-me read path

- Session inject + optional hydrate candidates from active facts only.

### Phase F — Human-facing contribution

- Spec: `docs/specs/TFL_PROTOCOL.md` (schema + question pack + metrics)  
- Blog/wiki: “Forget well” — why append-only agent md fails humanity-scale agents  
- Optional: upstream-friendly Apache/MIT protocol text (license already MIT)

---

## 7. What “contribute to humanity” means here (concrete, not slogan)

1. **Name the failure mode** clearly: append-only agent memory → indecision.  
2. **Ship a protocol** others can reimplement without buying a memory SaaS.  
3. **Prove forget/update** with open fixtures, not star-count theater.  
4. **Keep safety:** fail-closed writes + redaction + escalate_human for sensitive beliefs.  
5. **Refuse dishonest speed claims** so the field does not waste another cycle on wrong benchmarks.

---

## 8. Reviewer scorecard for *this PLAN* (target ≥9.5)

Ask David / Justin to score the PLAN on Leon dimensions, with PLAN-specific notes:

| Dimension | What “9.5” needs on this PLAN |
|-----------|-------------------------------|
| Evidence | Clear falsification hooks; cites live remember-me lessons (no acceleration myth) |
| Goal fit | Solves contradiction/growth; Jev role correct; humanity contribution concrete |
| Runtime | Architecture implementable on remember-me stack; pin model; fail-closed |
| Verification | Pre-registered metrics + phases; CI path |
| Safety | Redaction, escalate, no dump-all on error |
| License | MIT / open protocol intent |
| Maintainability | Bounds scope; non-goals; migration from md dumps |

**Auto-REJECT ≥9.5 if PLAN:** claims Jev accelerates hydrate; relies on unbounded md; uses LLM free-text as ledger source of truth; omits forget; omits fail-closed write; omits eval bars.

---

## 9. Immediate next actions after PLAN ≥9.5

1. Open GitHub issues mapped to Phase B–F.  
2. Implement Phase B behind feature flag.  
3. Re-run reviewer loop on **implementation evidence**, separate from PLAN score.  
4. Independent human redact review remains open from prior AWC (do not skip).

---

## 10. Non-goals

- Replacing Supermemory / Mem0 / Zep as a hosted product in v0.  
- Vision/robot memory.  
- Using Jev to generate diary prose.  
- Automatic ≥9.5 PRODUCT claim when only PLAN is strong.

---

**End of PLAN draft.** Reviewers: please return scores + must-fix list. If &lt;9.5, this file will be revised in place until bars clear.
