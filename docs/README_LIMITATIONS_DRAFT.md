# README “Limitations” section — DRAFT for later merge

**Status:** DRAFT ONLY — merge into root `README.md` only after **dual approval**.  
**Do not** treat this file as the live README.  
**Written:** 2026-09-20 (CST / Asia/Taipei)

---

## Proposed replacement / expansion for README “Limitations (honest)”

```markdown
## Limitations (honest)

- **PREVIEW / Pre-Skill** — not a formal promoted skill. See [SCORECARD.md](SCORECARD.md) (~8.5 weighted, FakeJev evidence basis).
- **Offline bake-off ≠ live proof.** `remember-me bakeoff` uses **FakeJev** (deterministic, no network). Published `bakeoff_metrics.json` must not be read as TypeSafe cloud latency or calibrated decision quality. See [docs/HONEST_LIMITS.md](docs/HONEST_LIMITS.md) and [docs/BAKEOFF_PLAN.md](docs/BAKEOFF_PLAN.md).
- **No live acceleration claim.** We do **not** claim that Jev “accelerates memory” versus Hindsight or dump-all until a live HttpJev bake-off (p50/p95, hydrate tokens, labeled keep/drop, fail-closed rate) is logged. Vendor ~70–500 ms System One latency implies the gate usually **adds** RTT; any win must be quality/token efficiency, not “faster FakeJev.”
- **HttpJev is scaffolding until proven.** Default client path may not match the public System One contract (`POST /v1/systemone`, `state` + typed `questions`). Do not advertise cloud mode as working without a successful redacted call log. See [docs/RUNTIME_HOWTO.md](docs/RUNTIME_HOWTO.md).
- **Gate layer, not a memory OS.** We do not replace Mem0, embedders, or TEMPR ranking. Jev must not re-rank local candidates.
- **Not a drop-in Claude / Codex / Hermes skill.** Official TypeSafe skills teach System One API usage; community Jev plugins mostly **compact tool results**. remember-me would plug as library + optional custom skill/hooks — see [docs/INTEGRATION_MATRIX.md](docs/INTEGRATION_MATRIX.md). Hermes `SOUL.md` is generic identity, not a memory hydrate engine.
- **No theater metrics.** No fake star counts, Fortune 500 logos, or invented production case studies.
```

---

## Merge checklist (dual approval)

- [ ] Leon approval #1
- [ ] Second reviewer / dual approval #2
- [ ] Links resolve in published repo tree
- [ ] No live latency numbers added without `bakeoff_metrics_live.json`
- [ ] README badge still says PREVIEW / Pre-Skill
