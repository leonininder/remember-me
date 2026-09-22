# PLAN — Temporal Fact Ledger (TFL) + Jev reconciliation

**Status:** REVISED draft after Justin ~8.5 (must-fixes 1–11) + David ≈8.7 (must-fixes 1–12); awaiting re-score + David / Justin  
**Owner:** Leon (via 小助手)  
**Repo tip context:** remember-me PREVIEW / AWC (~8.6–8.8) after enrich v2 + remote CI; Leon signed PREVIEW/AWC 2026-09-22  
**Codename:** Temporal Fact Ledger (TFL) — working title; supersedes “append-only memory.md” as the memory hygiene path  
**Rule:** Iterate this PLAN until both reviewers score it **≥9.5/10** or explicitly list remaining PLAN gaps; do not start large Phase B–F code until the PLAN clears **or** Leon waives in writing.

**Review trail:** `docs/reviews/JUSTIN_SUN_2026-09-22_TFL_PLAN.md` (REJECT ~8.5); `docs/reviews/DAVID_TFL_PLAN_2026-09-22.md` (REJECT ≈8.7).

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

## 2. Evidence primacy (remember-me live lessons)

Primary Evidence for this PLAN is **remember-me live work**, not video narration:

| Lesson | Source | Implication for TFL |
|--------|--------|---------------------|
| Enrich / hydrate with Jev can raise quality while **latency ≫ baseline** | Live enrich v2 pilot 2026-09-22 (~155k input tokens / 50q anti-pattern) | **Never** claim “Jev accelerates memory retrieval.” Use Jev only on **structured reconcile pairs** with hard token/K caps. |
| Fail-closed + redaction + audit are non-negotiable on write paths | Gates / redact / GateAuditRecord culture | Ledger APPLY is fail-closed; chat UX may fail-open elsewhere. |
| Thresholds must not be lowered into noise | Held-out conf band discipline | Phase A: **no threshold tune**; T_accept=0.85 / T_escal=0.55 held unless holdout proves separable. |
| Fan-out without bounds burns tokens | Enrich v2 fan-out | Soft cap ≤3k input tokens / reconcile event avg; batch ≤5 incumbents; over → escalate_human / defer / quarantine — never silent md-append. |
| PRODUCT score ≠ PLAN score | Leon PREVIEW/AWC sign-off | Clear PLAN ≥9.5 first; product evidence is a separate loop. |

Video lesson bullets (secondary inspiration only) live in **Appendix A**.

---

## 3. Design principles (non-negotiable)

1. **Beliefs are versioned facts, not transcripts.** Store `FactKey` + `FactVersion` with `valid_from` / `valid_to` / `superseded_by` / `conflicts_with[]`.  
2. **Jev decides mutation class; code applies it.** No free-text “memory rewrite” from an LLM as source of truth.  
3. **Fail-closed on write.** If Jev denied / timed out / malformed / unavailable → **no** silent append; **QuarantineQueue** or escalate. (Chat UX may fail-open elsewhere; the ledger must not.)  
4. **Redaction-first state.** Reconciliation state is structured fields + short stubs + hashes; no dump of full diaries by default (`include_raw_query=False` unless Leon risk-accepts).  
5. **Forget is a feature.** TTL, topic replace, and explicit tombstones are success metrics, not bugs.  
6. **Do not claim “Jev accelerates memory retrieval.”** Claim: **Jev accelerates belief reconciliation vs LLM arbitration** and **keeps context small** — and only when **joint** latency+quality bars pass.  
7. **Human contribution:** publish an open **Temporal Fact Ledger protocol** (schema + gate question set + eval harness) others can implement — not only a private Leon wiki dump.  
8. **LLM may propose structs; code validates.** Invalid / unknown → quarantine / escalate; **never** append prose into the ledger.

---

## 4. Architecture

```text
Event (chat turn / tool result / file / sensor)
    → CandidateFactExtractor (deterministic + optional LLM propose)
    → SchemaValidate + ontology allowlist  [reject → quarantine.*; never prose SoT]
    → TopicIndex.lookup(same FactKey [+ optional ontology/embedding neighbors])  [local, not Jev]
    → JevReconcileGate(state={new, ≤K incumbents_redacted}, questions=…)
    → Policy → APPLY: upsert | supersede | expire | tombstone | escalate_human | no_op
         (v0: NO merge)
    → Ledger (SQLite/JSONL, ledger_schema_version) + Audit (GateAuditRecord)
         OR QuarantineQueue if gate unavailable / needs_human
    → ProfileCompiler (static + dynamic slices) for session inject / remember-me hydrate candidates
```

### 4.1 Relation to existing remember-me

| Layer | remember-me today | TFL adds |
|-------|-------------------|----------|
| Retrieve | topology / local top-k | FactKey index + temporal as-of query |
| Gate | hydrate / emit / writeback | **reconcile / forget / supersede** |
| Store | markers + content_ref | **versioned fact ledger** |
| Profile | implicit via tags | **compiled static/dynamic profile** |
| Offline | (various) | **QuarantineQueue** — never md-append fallback |

TFL is the **write-side belief engine**; remember-me hydrate remains the **read-side admit gate**. Same redaction + audit culture.

### 4.2 CandidateFact schema (v0) — Justin #1 / David #1

JSON Schema-ish closed fields. **Only** these may enter the gate; unknown properties → reject.

```json
{
  "$id": "candidate_fact.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["entity", "attribute", "value_struct", "observed_at", "source_event_id", "extract_method"],
  "properties": {
    "entity": {
      "type": "string",
      "description": "Allowlisted entity id, e.g. user, home, agent; lowercase snake; max 64"
    },
    "attribute": {
      "type": "string",
      "description": "Allowlisted attribute from ontology enum OR quarantine bucket attribute"
    },
    "qualifier": {
      "type": ["string", "null"],
      "description": "Optional disambiguator, e.g. today, local; lowercase snake; max 64"
    },
    "value_struct": {
      "type": "object",
      "description": "Structured value only — never a free-text diary blob as SoT",
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string",
      "format": "date-time",
      "description": "Producer-claimed observation time (metadata; see clock-skew policy)"
    },
    "source_event_id": { "type": "string" },
    "extract_method": {
      "type": "string",
      "enum": ["deterministic", "llm_propose", "manual"]
    },
    "proposed_fact_key": {
      "type": ["string", "null"],
      "description": "Optional LLM suggestion; ignored unless validator accepts ontology path"
    },
    "salience_hint": {
      "type": ["string", "null"],
      "enum": ["childhood_play", "adult_safety", "routine", "ephemeral", null]
    }
  }
}
```

**Rules:**

- `extract_method=llm_propose`: LLM may emit a CandidateFact **struct**; code runs schema validate + ontology allowlist.  
- **Never** becomes ledger SoT until validate passes.  
- Invalid / unknown entity|attribute → route to `quarantine.*` FactKey bucket or escalate; **never append prose**.  
- `value_struct` MUST NOT be a single unstructured `{"text": "<diary>"}` as the only content for admit; diary stubs may appear only as redacted `stub_hash` fields for audit, not as active belief value.

### 4.3 FactKey minting, normalization, caps — Justin #1 / David #2

**Canonical FactKey** = normalized `entity.attribute[.qualifier]` (lowercase snake).

| Rule | Spec |
|------|------|
| Normalize | NFKC → lowercase → non `[a-z0-9_]` → `_`; collapse `__`; trim `_`; max component 64 chars; max full key 192 |
| Who invents keys | **Code** from validated ontology enum OR quarantine bucket `quarantine.<hash8>` / `quarantine.<entity>.<attr>` |
| LLM | May propose `proposed_fact_key` / struct fields; **never** invents ledger SoT keys without validate |
| Deterministic hash | Optional secondary id: `sha256(fact_key)[:16]` for storage; human key remains primary |
| Collision | Same normalized string = same FactKey. Distinct value shapes for same key → reconcile (same_fact / supersedes / contradicts), not silent dual-active |
| Multi-value | v0: one **active** value_struct per FactKey. Lists inside `value_struct` OK if schema allows; no parallel active versions |
| Namespace / ownership | Prefix entity = owner scope (`user.*`, `home.*`, `agent.*`, `quarantine.*`). Cross-entity write requires escalate_human |
| Caps | Max **active** FactKeys per entity: **64** (soft); over → expire lowest-salience ephemeral or escalate. Max active versions globally soft-warned at 512 |

### 4.4 Data model (v0)

```text
ledger_schema_version: "tfl_ledger_v0"

FactKey:      "entity.attribute[.qualifier]"   # see §4.3
FactVersion:  {
                version_id, fact_key, value_struct,
                valid_from, valid_to?,
                receive_ts,              # server authoritative ordering key
                observed_at,            # metadata only
                source_event_id, confidence, salience_tier,
                ttl_hint?,
                status: active|superseded|expired|tombstoned|quarantined,
                superseded_by?, conflicts_with[]?,  # cross-key links
                should_forget_incumbent_applied?: bool
              }
ReconEvent:   { ts, new_candidate, incumbent_ids, jev_answers, action, audit_id }
QuarantineItem: { id, candidate, reason, enqueued_at, attempts, escalate_after }
```

**Same-key weather example:**  
- Day1: `weather.local = sunny` valid_from=D1  
- Day2: Jev `supersedes` same FactKey → Day1 `valid_to=D2`, Day2 active  
- Ask “what’s the weather belief *as of now*?” → one row

**Insects / salience path:**  
- Child: `insects.play = attractive`, `salience_tier=childhood_play`  
- Adult: new candidate `insects.safety = caution_toxic_species`, `salience_tier=adult_safety`  
- Jev `relation=contradicts` + high `adult_safety` → APPLY supersede winner + demote old from ProfileCompiler (see §4.6)

### 4.5 Cross-key contradiction policy — Justin #2

**Normative:**

1. `TopicIndex` may return same-FactKey hits **and** (Phase C2+) ontology / embedding neighbors.  
2. MVP (Phase B+C): **same-FactKey only**; embedding-neighbor deferred (see §6 MVP cut). When neighbors enabled, pin local embed model in PLAN addendum before use.  
3. If Jev returns `relation=contradicts` across **different** FactKeys (e.g. `weather.local` vs `weather.forecast_today`):  
   - APPLY = **supersede** the **winner key’s** active version (new candidate becomes active on its key), **and**  
   - if `should_forget_incumbent=true` (Noul high / above T_accept): set loser keys’ active versions to `superseded` or `tombstoned` per policy, with `should_forget_incumbent` recorded, **and**  
   - link both sides via `conflicts_with[]` on each FactVersion.  
4. Winner selection: prefer higher `receive_ts`; if tie / undecidable → `escalate_human` (fail-closed).

**Worked example (same day, different keys):**

| | Key | value | receive_ts |
|-|-----|-------|------------|
| Incumbent | `weather.local` | `{condition: sunny}` | T0 |
| New | `weather.forecast_today` | `{condition: rainy}` | T1 (>T0) |

- TopicIndex returns neighbor pair; Jev: `relation=contradicts`, `should_forget_incumbent=true`, `needs_human=false`, `salience_tier` routine.  
- APPLY: activate rainy on `weather.forecast_today`; supersede sunny on `weather.local`; set `conflicts_with` both ways; ProfileCompiler injects rainy only.

### 4.6 Jev question pack + APPLY map — Justin #3 / David #3 / David #11

All Choice criteria = **dict** `{key: description}`; Score = ordered **string** levels; pin `jev-1.13.0`.

| Question id | Type | Purpose |
|-------------|------|---------|
| `relation` | Choice | `same_fact` \| `supersedes` \| `contradicts` \| `side_thread` \| `noise` \| `other` |
| `should_forget_incumbent` | Noul | Incumbent should leave active set |
| `ttl_urgency` | Score | permanent → hours |
| `profile_worthiness` | Noul | Belongs in static/dynamic profile inject |
| `needs_human` | Noul | Sensitive → escalate (see taxonomy) |
| `salience_tier` | Choice **or** Score | `childhood_play` \| `adult_safety` \| `routine` \| `ephemeral` |

**v0 APPLY list (merge DROPPED — non-goal):**  
`upsert | supersede | expire | tombstone | escalate_human | no_op`

#### Policy table: relation × should_forget × needs_human → action

| relation | should_forget | needs_human | salience note | APPLY |
|----------|---------------|-------------|---------------|-------|
| `same_fact` | any | false | — | **upsert** salience/TTL/confidence only; **no** dual row; no new version unless value_struct materially changed (then treat as supersedes) |
| `supersedes` | true | false | — | **supersede** (incumbent valid_to=now; new active) |
| `supersedes` | false | false | — | **upsert** new version still; incumbent may remain until TTL — prefer expire if ttl_urgency high |
| `contradicts` | true | false | — | **supersede** winner; forget/demote loser (incl. cross-key §4.5) |
| `contradicts` | true | false | **adult_safety** high vs childhood_play | **supersede** + **demote** old from ProfileCompiler (insects path) |
| `contradicts` | false | false | — | keep both active only if different keys **and** not neighbors; else **escalate_human** |
| `side_thread` | — | false | — | **upsert** on a **new** FactKey (code mints from ontology); incumbent untouched (**no_op** on incumbent) |
| `noise` | — | false | — | **no_op** (optionally quarantine candidate) |
| `other` | — | false | — | **escalate_human** or quarantine |
| *any* | *any* | **true** | — | **escalate_human** (deny auto-write); see taxonomy |
| gate error / timeout | — | — | — | **QuarantineQueue** — never md-append |

`expire` / `tombstone`: driven by `ttl_urgency`, explicit user forget, or policy cron — not only Jev relation.

#### `needs_human` closed taxonomy → deny vs escalate — David #11

| Class | Examples | Write policy |
|-------|----------|--------------|
| `identity` | legal name, national id, biometrics | **deny_write** auto; dual-control admit only |
| `medical` | diagnoses, meds, therapy notes | **escalate_human**; no auto supersede |
| `legal` | contracts, court, counsel | **escalate_human** |
| `financial` | account numbers, balances, tax id | **deny_write** auto / escalate |
| `minors` | anything about persons <18 / school records | **deny_write** auto; escalate |
| `location_precise` | lat/long home, exact address change | escalate (coarse city may upsert) |
| `other_sensitive` | catch-all when Noul high | escalate |

Default when taxonomy class unknown but `needs_human=true`: **escalate_human** (fail-closed).

### 4.7 Incumbent bounds, redact allowlist, cost — Justin #7 / David #5 / David #10

| Bound | v0 value |
|-------|----------|
| Max incumbents K to Jev | **5** (local rank only; Jev never ranks retrieval) |
| Soft input token cap / reconcile event | **≤3k** average; hard abort → escalate_human / defer / quarantine |
| Max reconciles / user turn | **3**; further candidates → quarantine / defer |
| Batching | Batch ≤5 incumbents in one gate call when same TopicIndex cluster |
| Anti-pattern warning | remember-me enrich v2 ~**155k in / 50q** — naïve fan-out forbidden |

**Reconcile outbound allowlist (named):** `RECONCILE_STATE_ALLOWLIST` — fields permitted in Jev state:  
`fact_key`, `value_struct` (schema-clipped), `valid_from`, `receive_ts`, `salience_tier`, `confidence`, `stub_hash`, `conflict_keys[]`.  
**Forbidden by default:** raw diary, full transcripts, secrets, emails, phone, exact street.

**Escalation snapshot allowlist (named):** `ESCALATION_SNAPSHOT_ALLOWLIST` — same as reconcile plus `source_event_id`, `extract_method`, `quarantine_reason`; still no raw diary unless Leon risk-accepts with audit.

### 4.8 QuarantineQueue — David #6

When Jev **deny / timeout / malformed / unavailable** OR schema fail OR cost abort:

1. Enqueue `QuarantineItem` (bound size **N=256**; oldest durable to disk spill or drop-with-audit if overflow — **never** md-append).  
2. Drain: human review UI / CLI admit, or retry when Jev healthy, or escalate_human.  
3. **Explicit ban:** no fallback writing CandidateFact prose into `MEMORY.md` / `AGENTS.md` as SoT.

### 4.9 Threat notes — Justin #8

| Threat | Fail-closed behavior |
|--------|----------------------|
| (a) Prompt-injected CandidateFact | Schema / allowlist fail → **quarantine**; never ledger append |
| (b) Poisoned incumbent | If identity / medical / financial class or `needs_human` → **escalate_human** / dual-control; do not auto-supersede from untrusted new candidate alone |
| (c) Clock skew on `valid_from` / `observed_at` | Authoritative ordering key = server **`receive_ts`**; `observed_at` is metadata only. If ordering undecidable (equal receive_ts + conflicting values) → **escalate_human**, no APPLY |

---

## 5. Falsifiable success metrics (pre-register before build)

### 5.1 Metric table

| Metric | Pass bar (v0) | Falsify if |
|--------|---------------|------------|
| Active ledger size @ N events | ≤ O(unique FactKeys) not O(N) | Grows ~linear with events |
| Dual-active same FactKey | **0** | Any dual-active |
| Contradiction visible to prompt | 0 dual-active same FactKey; cross-key conflicts resolved or escalated | ≥1% queries see unresolved dual belief |
| Reconciliation decision latency | Jev path p95 **and** quality co-bar (§5.2) | Latency-only “win” |
| Wrong supersession rate | ≤ **2%** on labeled suite | >5% |
| Fail-closed on gate errors | 100% no apply; quarantine or escalate | Any apply on deny/timeout |
| Profile inject freshness | Stale/superseded FactKey in **default** ProfileCompiler output = **0** on suite; token budget ≤**1500** typical (**p50**) | Any stale key; p50 >1500 |
| Cost | ≤3k input tokens / reconcile event average | Systematic overage without escalate |

**Explicit non-metric:** “faster than local retrieve without Jev” — out of scope / previously falsified for hydrate.

### 5.2 Joint latency + quality bar — Justin #4

**Forbid celebrating latency alone.**

| Item | Pin |
|------|-----|
| LLM-as-judge default | `openai/gpt-4o-mini` (named default). Alt if pinned later: `gpt-4.1-mini` or `claude-haiku-4.5` — document swap in freeze-id |
| Prompt | fixed hash placeholder `llm_judge_prompt_v0` (SHA recorded at freeze) |
| n | ≥**200** labeled pairs for latency bakeoff (subset of suite or dedicated) |
| Machine class | report `box-cpu` or CI runner id in EVIDENCE |
| **Pass only if both** | (1) Jev reconcile **p95 <** LLM-judge p95 on **same** pairs, **and** (2) wrong-supersession ≤**2%** |

### 5.3 Eval suite contract + freeze — Justin #5 / David #4

**Fixture stub tree (in-repo under plan commitment):**

```text
fixtures/memorybench_tfl/
  README.md
  schema/candidate_fact.schema.json
  suites/weather_flip/
  suites/address_move/
  suites/preference_reversal/
  suites/childhood_adult_safety/
  labels/pairs.jsonl
```

| Contract | v0 |
|----------|----|
| Min labeled pairs | ≥**50** per relation class (`same_fact`, `supersedes`, `contradicts`, `side_thread`, `noise`) → ≥**250** total |
| Holdout | **20%** held-out if any threshold tune; **no threshold tune in Phase A** |
| freeze-id | e.g. `memorybench_tfl_v0_<YYYYMMDD>` recorded in EVIDENCE |
| Fixture SHA | `sha256` of `labels/pairs.jsonl` + suite dirs at freeze |
| Wrong-supersession label guide | A pair is **wrong supersession** if APPLY supersedes when gold `relation∈{same_fact,side_thread,noise}` OR gold says supersede/contradict **different** winner key than policy applied |
| Contradiction denominator | `# pairs with gold relation=contradicts` (same-key + cross-key labeled); rate = wrong outcomes / denominator |
| Pass/fail owners | PLAN author proposes; David + Justin re-score PLAN; Leon signs product later |

### 5.4 Profile inject metric — Justin #6

Pass: **0** stale/superseded FactKeys in default ProfileCompiler output on suite; token budget ≤**1500** p50.

---

## 6. Phased delivery + MVP cut — David #7 / #8 / #9

### Phase A — PLAN lock (≥9.5 from David + Justin on *this document*)

- Address all REJECT comments; revise PLAN in-repo; no large code until PLAN ≥9.5 **or** Leon waives in writing.

### Phase B — Ledger + deterministic tests (**MVP core**)

- SQLite/JSONL FactVersion store; `ledger_schema_version`; as-of query; supersede/expire/tombstone APIs; property tests (no dual-active).  
- **B0 (optional one-shot):** scripted `MEMORY.md` → CandidateFact lines (one fact per bullet heuristic) into **quarantine** for human/Jev admit — **not** silent auto-ledger. After import, md is **not** write SoT. Full auto-migration = **non-goal v0**.  
- Must alone start falsifying §5 size + dual-active.

### Phase C — JevReconcileGate (**MVP core**)

- HttpJev + FakeJev; chaos fail-closed; adversarial redact on reconcile state; live smoke logs; QuarantineQueue.  
- **Exit criterion:** independent **human redact review** of `RECONCILE_STATE_ALLOWLIST` / `ESCALATION_SNAPSHOT_ALLOWLIST` must pass before Phase C closes (not only a §9 reminder).  
- **C1 MVP:** same-FactKey reconcile only.  
- **C2 (deferred):** ontology/embedding neighbors — pin local embed model in addendum before enabling; until then embedding-neighbor is non-goal.

**MVP falsify gate:** Phase B+C must falsify §5 **size / dual-active / fail-closed** before ProfileCompiler / blog / protocol marketing expand.

### Phase D — Eval harness `memorybench_tfl`

- Open fixture pack + scripts; publish results as EVIDENCE / NON-EVIDENCE labeled honestly; joint latency+quality bakeoff.

### Phase E — ProfileCompiler + remember-me read path

- Session inject + optional hydrate candidates from active facts only; profile stale=0 + ≤1500 p50 bars.

### Phase F — Human-facing contribution

- Spec: `docs/specs/TFL_PROTOCOL.md` (schema + question pack + metrics) — seed already in §10 of this PLAN.  
- Blog/wiki: “Forget well” — why append-only agent md fails humanity-scale agents.  
- Optional: upstream-friendly Apache/MIT protocol text (license already MIT).

---

## 7. Migration — Justin #9 / David #9

| Path | v0 |
|------|----|
| Scripted import | `MEMORY.md` / similar → one CandidateFact per bullet heuristic → **quarantine** for human or Jev admit |
| Silent auto-ledger | **Forbidden** |
| Full auto-migration | **Non-goal v0** |
| After import | md files are **not** write SoT; ledger (+ quarantine drain) is SoT |
| Schema | every DB/JSONL header carries `ledger_schema_version: "tfl_ledger_v0"` |

---

## 8. CI jobs — Justin #11

Planned sibling workflow **`.github/workflows/tfl.yml`** (not only matrix noise inside `ci.yml`), paths filter:

- `src/remember_me/tfl/**`  
- `fixtures/memorybench_tfl/**`  
- `tests/tfl/**`  
- this PLAN / protocol specs as docs-only (no fail)

| Job name | Phase | What |
|----------|-------|------|
| `tfl-ledger-props` | B | Property tests: no dual-active; as-of; supersede invariants |
| `tfl-reconcile-unit` | C | FakeJev unit + chaos fail-closed + quarantine |
| `tfl-memorybench` | D | Harness on fixtures; **FakeJev default**; live Jev optional manual/`workflow_dispatch` |

Gate on `main` via `tfl.yml` required checks once jobs exist. Until code lands, jobs are **named commitments** in this PLAN.

---

## 9. What “contribute to humanity” means here (concrete, not slogan)

1. **Name the failure mode** clearly: append-only agent memory → indecision.  
2. **Ship a protocol** others can reimplement without buying a memory SaaS.  
3. **Prove forget/update** with open fixtures, not star-count theater.  
4. **Keep safety:** fail-closed writes + redaction + escalate_human for sensitive beliefs + quarantine offline.  
5. **Refuse dishonest speed claims** so the field does not waste another cycle on wrong benchmarks.

---

## 10. Protocol seed (normative weather supersession) — Justin #10

Minimal normative JSON seed (Phase F expands to `docs/specs/TFL_PROTOCOL.md`):

```json
{
  "protocol": "tfl_reconcile_v0",
  "ledger_schema_version": "tfl_ledger_v0",
  "example_id": "weather_local_sunny_to_rainy",
  "incumbent": {
    "fact_key": "weather.local",
    "value_struct": {"condition": "sunny"},
    "valid_from": "2026-09-21T10:00:00+08:00",
    "receive_ts": "2026-09-21T10:00:01+08:00",
    "status": "active",
    "salience_tier": "ephemeral"
  },
  "candidate": {
    "entity": "weather",
    "attribute": "local",
    "qualifier": null,
    "value_struct": {"condition": "rainy"},
    "observed_at": "2026-09-22T09:00:00+08:00",
    "source_event_id": "evt_weather_obs_20260922",
    "extract_method": "deterministic",
    "salience_hint": "ephemeral"
  },
  "minted_fact_key": "weather.local",
  "questions": [
    "relation",
    "should_forget_incumbent",
    "ttl_urgency",
    "profile_worthiness",
    "needs_human",
    "salience_tier"
  ],
  "sample_answers": {
    "relation": "supersedes",
    "should_forget_incumbent": true,
    "ttl_urgency": "hours",
    "profile_worthiness": true,
    "needs_human": false,
    "salience_tier": "ephemeral"
  },
  "APPLY": "supersede",
  "effect": {
    "incumbent_status": "superseded",
    "incumbent_valid_to": "2026-09-22T09:00:02+08:00",
    "new_status": "active",
    "conflicts_with": []
  }
}
```

---

## 11. Reviewer scorecard for *this PLAN* (target ≥9.5)

Ask David / Justin to score the PLAN on Leon dimensions, with PLAN-specific notes:

| Dimension | What “9.5” needs on this PLAN |
|-----------|-------------------------------|
| Evidence | Clear falsification hooks; cites live remember-me lessons as primary (no acceleration myth); videos demoted |
| Goal fit | Solves contradiction/growth; Jev role correct; FactKey/CandidateFact/APPLY complete; humanity contribution concrete |
| Runtime | Architecture implementable; pin jev + judge model; K-cap; quarantine; fail-closed |
| Verification | Pre-registered metrics + freeze + suite N + CI job names |
| Safety | Redaction allowlists, escalate taxonomy, threats, human-redact Phase C exit |
| License | MIT / open protocol intent |
| Maintainability | MVP cut B+C; schema_version; md import → not SoT; non-goals |

**Auto-REJECT ≥9.5 if PLAN:** claims Jev accelerates hydrate; relies on unbounded md; uses LLM free-text as ledger SoT; omits forget; omits fail-closed write; omits eval bars; celebrates latency without quality co-bar.

---

## 12. Immediate next actions after PLAN ≥9.5

1. Open GitHub issues mapped to Phase B–F (MVP = B+C first).  
2. Implement Phase B behind feature flag; add `tfl.yml` stubs.  
3. Re-run reviewer loop on **implementation evidence**, separate from PLAN score.  
4. Independent human redact review = Phase C **exit** (do not skip).

---

## 13. Non-goals

- Replacing Supermemory / Mem0 / Zep as a hosted product in v0.  
- Vision/robot memory.  
- Using Jev to generate diary prose.  
- Automatic ≥9.5 PRODUCT claim when only PLAN is strong.  
- **`merge` APPLY** in v0.  
- Full auto-migration of historical md dumps into the ledger.  
- Embedding-neighbor TopicIndex before Phase C2 + pinned embed model.  
- Celebrating reconcile latency without joint quality bar.

---

## Appendix A — Video lesson bullets (secondary; demoted per David #12)

### A.1 Jev speed demos (e.g. `T4zKauxr7Ug`)

- Fast on closed decisions via typed options; not proven as “memory accelerate.”  
- TFL: Jev on structured fact pairs only.

### A.2 Supermemory (`SHRkOI0yO4Q`)

- Memory ≠ RAG; update / forget / proactive profile.  
- TFL adopts those as first-class with Jev-native gate + local ledger.

### A.3 Gary Chen / System One gate framing (`2mtn-Qp59y4` lineage)

- Dual-gate; escalate_human; Jev admits, does not rank.  
- TFL write path admits fact mutations, not prose dumps.

### A.4 Critique videos (e.g. 抡锤者)

- No Jev-in-chat theater.  
- TFL must show measurable hygiene metrics.

---

**End of PLAN (revised).** Reviewers: please re-score. If &lt;9.5, this file will be revised in place until bars clear.
