# Launch distribution checklist (Jarvis → Leon)

Document type: Process / launch pattern  
Audience: Leon project launches (devtools, skills, libraries)  
Status: Living checklist — extract pattern from [jev-chat/jev-chat-jarvis](https://github.com/jev-chat/jev-chat-jarvis) virality; adapt honestly  
Date: 2026-09-26 (Asia/Taipei)  
Canonical copies:

- Shared wiki: `03_wiki/process/launch_distribution_checklist_from_jev_jarvis_en.md`
- CML project pointer: `04_projects/Camera_Motion_Language/launch_distribution_checklist_en.md`
- remember-me repo: `docs/LAUNCH_CHECKLIST.md`

**Honesty rule:** never invent stars, sponsors, bake-off wins, live Jev proof, or production case studies. Mark missing proof `TODO` or omit.

---

## Why this exists

Jarvis (Android chat co-pilot) grew fast because the README was a **distribution shell**: one-line pitch, installable artifact in minutes, above-the-fold screenshots, multi-platform siblings, sponsor strip, fear FAQ, privacy page, versioned Releases, bilingual CN entry, and a contributor hook (“adapter ≈ N lines”).

Leon launches (e.g. **remember-me**, **Camera Motion Language**) are not consumer APKs — but the **same shell** transfers if you map each tactic to a developer-project equivalent.

---

## Jarvis → Leon mapping table

| # | Jarvis tactic | Developer-project equivalent (Leon) | remember-me example | CML example |
|---|---------------|-------------------------------------|---------------------|-------------|
| 1 | One-line pain→outcome pitch | ≤15-word hook under title | “Agents forget. Remember Me decides what to hydrate.” | “Keyed vs sampled camera; Static Shot default; 8% drift gate.” |
| 2 | Installable artifact &lt;2 min (signed APK) | `pip install -e .` + one demo command | `pip install -e ".[dev]"` → `remember-me demo` | `python measure_frame_drift.py --video …` on a golden |
| 3 | Above-the-fold screenshot / GIF | Hero GIF or terminal capture in `assets/` | `assets/demo.gif` (or capture instructions until present) | Before/after PASS/FAIL stills + filled shot-card |
| 4 | Multi-surface siblings (Android / Mac / Win) | Library · CLI · Cookbook · ZH · Bake-off (or skill + script + goldens) | README surfaces row | Skill SOP + drift script + `golden_clips/` |
| 5 | Sponsor / social-proof strip | Honest strip only; placeholders `TODO` | Omit or `TODO: real sponsor only` | Same |
| 6 | Community funnel (公众号私信 / QR) | GitHub Issues (+ Discussions if enabled); optional Discord/公众号 | Issues (Discussions off as of 2026-09-26) | Wiki + Issues if repo exists |
| 7 | Separate homepage (optional) | Optional; GitHub README may be enough | No separate site required | Wiki project folder is the home |
| 8 | Privacy / honesty page | `SECURITY.md` / `PRIVACY.md` / `HONEST_LIMITS.md` | SECURITY + HONEST_LIMITS | Drift evidence honesty + SYNTHETIC goldens label |
| 9 | GitHub topics | 8–12 searchable topics | Applied on GitHub (see CONTRIBUTING list) | n/a for wiki-only |
| 10 | Versioned Releases | GitHub Releases + changelog | Tag `v0.x` when ready; keep PREVIEW honest | Skill status LOCKED date ≠ product Release |
| 11 | Built-with-Jev / System One | Decision-gate framing, not chat LLM | “Built with TypeSafe Jev (System One)” | CML does not require Jev; omit unless true |
| 12 | Fear FAQ | Collapse: secrets? bodies? root? auto-send? | FAQ → SECURITY | FAQ: does gate claim H3 always PASS? (no) |
| 13 | Changelog + version badge | Badge + CHANGELOG or Releases notes | Version badge when tagging | Status line with lock date |
| 14 | Contributor hook (adapter N lines) | “Integrate in ~10 lines” / gate recipe | Cookbook + INTEGRATION_MATRIX | “Adopt skill without full wiki” mini pack |
| 15 | Bilingual ZH entry | `docs/GETTING_STARTED_ZH.md` linked near top | Prominent ZH link | Optional ZH stub later |

---

## Pre-flight checklist (top items)

Copy this block into a launch PR or wiki index when shipping.

### Pitch & install

- [ ] **One-line pitch** (≤15 words) under the title — pain → outcome.
- [ ] **Installable artifact &lt;2 minutes** — APK ↔ `pip install -e .` + demo CLI; document exact commands.
- [ ] **Above-the-fold media** — screenshot/GIF; if missing, `assets/README.md` with capture steps (no fake media).

### Surfaces & proof

- [ ] **Multi-surface siblings** named above the fold (Library · CLI · Cookbook · ZH · Bake-off / skill · script · goldens).
- [ ] **Sponsor / social-proof** — only real names; else omit or mark `TODO`.
- [ ] **Built-with-Jev / System One** framing when true — decision gate, not chat LLM; no live-proof claims without logs.
- [ ] **Fear FAQ** — auto-hydrate secrets? Jev sees bodies? root/Xposed? point to SECURITY / honesty docs.
- [ ] **Privacy / honesty page** linked from README (SECURITY, HONEST_LIMITS, PRIVACY as applicable).

### Discovery & community

- [x] **GitHub topics** set on `leonininder/remember-me` (python, memory-gate, typesafe, jev, system-one, agent-memory, redaction, fail-closed, decision-gate, llm-agents).
- [ ] **Versioned Releases** + changelog / version badge (or explicit PREVIEW with no fake badge).
- [x] **No GitHub Release yet** for remember-me — **PREVIEW** badge is the version signal (do not invent a hollow Release).
- [ ] **Community funnel** — Issues and/or Discussions; CN: ZH guide + optional 公众号 (do not invent QR).
- [ ] **Contributor hook** — “adapter N lines” ↔ “gate recipe / integrate in 10 lines” / adopt-skill mini pack.
- [ ] **Bilingual ZH entry** linked near top for CN discovery.
- [ ] **Optional homepage** — only if it adds signal beyond README/wiki.

### Anti-patterns (never)

- [ ] Do **not** fabricate star counts, Fortune logos, bake-off deltas as live proof, or “Jev accelerates X” without measured live RTT.
- [ ] Do **not** claim FakeJev / synthetic goldens as product / H3 proof.
- [ ] Do **not** put empty sponsor logos or expired QR codes without a working funnel.

---

## Worked pitch examples (honest)

| Project | Pitch (≤15 words) |
|---------|-------------------|
| Jarvis (reference) | On-phone chat co-pilot: judge first, draft replies, you always send. |
| remember-me | Agents forget. Remember Me decides what to hydrate. |
| Camera Motion Language | Split keyed vs sampled camera; default Static Shot; enforce 8% drift. |

---

## remember-me launch shell (concrete)

```bash
# <2 min artifact
pip install -e ".[dev]"
remember-me demo
```

Surfaces: Library · CLI · [Cookbook](COOKBOOK.md) · [ZH](GETTING_STARTED_ZH.md) · Bake-off  
Checklist file in-repo: this document when copied to `docs/LAUNCH_CHECKLIST.md`.

GitHub topics (applied on the repo; keep CONTRIBUTING list in sync):

```text
python memory-gate typesafe jev system-one agent-memory
redaction fail-closed decision-gate llm-agents
```

---

## CML launch shell (concrete)

Demo artifact: `golden_clips/` (SYNTHETIC) + one-command drift:

```bash
python <LLM_WIKI_ROOT>/04_projects/Camera_Motion_Language/measure_frame_drift.py \
  --video <out_or_golden.mp4> --intent static --threshold-pct 8
```

Share pack for adopters without the full wiki: skill SOP + shot-card schema + drift script + one filled shot-card + one PASS/FAIL example. See CML `launch_distribution_checklist_en.md` for the project-specific adaptation.

---

## Related

- Jarvis README pattern source: https://github.com/jev-chat/jev-chat-jarvis
- TypeSafe System One / Jev: https://typesafe.ai (decision model — no prose generation)
