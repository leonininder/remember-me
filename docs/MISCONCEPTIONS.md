# Common misconceptions — remember-me / Jev

**Written:** 2026-09-20 (CST / Asia/Taipei)

Short list of mistakes that break the gate or overclaim the product.

---

## 1. Using Jev for generation

**Wrong:** “Ask Jev to write the reply / summarize the memory body.”  
**Right:** System One answers **typed** Choice / Score / Noul only. It **cannot generate prose**. Your LLM (or template) writes; Jev decides.

---

## 2. Confidence ≠ correctness

**Wrong:** “0.92 confidence means the fact is true.”  
**Right:** Confidence is a calibrated **decision** signal for *this* question under *this* state. Application policy still owns thresholds (remember-me: 0.85 / 0.55). High confidence is **not** permission to leak raw content or skip redaction.

---

## 3. Overlapping Choice criteria

**Wrong:** Criteria like `["yes", "y", "true", "hydrate"]` that blur into each other.  
**Right:** Closed, disjoint taxonomies — e.g. `hydrate_full | stub_only | skip | promote_durable | other`. Overlap makes calibration and policy meaningless.

---

## 4. Raw query egress

**Wrong:** Shipping the full user ask (or memory bodies) in every System One `state`.  
**Right:** Default egress is **`query_hash`** only; `query_preview` is opt-in (`include_raw_query=True`). Outbound candidates are **redacted** metadata — no `content` / secrets. See [RUNTIME_HOWTO.md](RUNTIME_HOWTO.md).

---

## 5. FakeJev ≠ live

**Wrong:** Citing `remember-me bakeoff` FakeJev precision/latency as TypeSafe cloud proof.  
**Right:** FakeJev is a **deterministic offline** stub for CI and demos. Live quality/latency need a redacted HttpJev pilot log. See [HONEST_LIMITS.md](HONEST_LIMITS.md).

---

## 6. One question, one atom

**Wrong:** One giant Choice that mixes “should we hydrate?” with “what kind is it?” and “route the network.”  
**Right:** Separate atoms — hydrate Choice, need Score, still_matters Noul, optional network/reflect. Batch many candidates in one POST by prefixing keys `{node_id}__{question_id}`, not by stuffing many decisions into one criterion list.

---

## Related

- [COOKBOOK.md](COOKBOOK.md)
- [GETTING_STARTED_ZH.md](GETTING_STARTED_ZH.md)
- [HONEST_LIMITS.md](HONEST_LIMITS.md)
