# Integration matrix — Claude Code / Codex / Hermes

**Written:** 2026-09-20 (CST / Asia/Taipei)  
**Question:** Can remember-me plug into these agents? How does that differ from community Jev usage?

---

## Executive summary

| Host | Official TypeSafe Jev skill? | Auto-intercept memory? | remember-me plug shape | Strength |
|------|------------------------------|------------------------|------------------------|----------|
| **Claude Code** | Yes (plugin marketplace) | Compaction hooks exist (community); **not** memory hydrate | Library + optional custom skill/hooks — **not drop-in** | Strongest hook surface (`PreCompact`, `UserPromptSubmit`, …) |
| **Codex** | Via `npx skills` / Agent Skills | Implicit skill match on description; weaker than Claude hooks | `SKILL.md` under `.agents/skills/` + library calls — **not drop-in** | Medium — skills progressive disclosure, no compact hooks like Claude |
| **Hermes** | No first-party remember-me; **hermes-jev-compact** plugin for prune | `context.engine: jev` opts into **tool-result compaction** | Separate from SOUL.md; would need a memory plugin/engine — **not drop-in** | Compaction path exists; topology hydrate does **not** |

**Bottom line:** Community Jev = **decide / compact / route**. remember-me = **post-recall hydrate gate**. Compatible idea, different product surface. No host today auto-wires remember-me.

---

## What the community actually does with Jev

| Pattern | Project / doc | What Jev decides | Relation to memory stores |
|---------|---------------|------------------|---------------------------|
| System One primitives | [docs.typesafe.ai](https://docs.typesafe.ai/agent-skill), [Flavio deep dive](https://flaviocopes.com/jev/) | Choice / Score / Noul; **cannot speak** | Not a DB |
| Confidence floors | Same + [Vercel KB](https://vercel.com/kb/guide/typesafe-jev-and-ai-sdk) | App policy (e.g. conf≥0.6 and p≥0.7) | Policy in **your** code |
| Version pinning | Response `model: jev-1.13.0` | Stability for threshold calibration | Best practice |
| Claude skill | [typesafe-ai/skills](https://github.com/typesafe-ai/skills), [agent-skill docs](https://docs.typesafe.ai/agent-skill) | Teach agents correct API | Integration aid, not memory |
| fast-jev-compaction | Community Claude plugin (tamaratran/fast-jev-compaction) | Keep/drop/truncate **tool calls/results**; verbatim otherwise | **Context size**, not recall graph |
| hermes-jev-compact | [PyPI](https://pypi.org/project/hermes-jev-compact/) | Noul: call still matter? full result still matter? | Overrides Hermes compressor seam |
| LiteLLM jev-compaction | [LiteLLM blog](https://docs.litellm.ai/blog/typesafe-jev-compaction) | Relevance of older tool results | Proxy guardrail `pre_call` |

**None of the above is a topology memory store or TEMPR replacement.** remember-me must keep local retrieve and use Jev only as admit/hydrate gate (architecture freeze).

---

## Claude Code

### Official TypeSafe skill (evidence)

```bash
claude plugin marketplace add typesafe-ai/skills
claude plugin install typesafe@typesafe-ai
# invoke: /typesafe:typesafe-ai
```

- Docs: https://docs.typesafe.ai/agent-skill  
- SKILL.md: https://raw.githubusercontent.com/typesafe-ai/skills/main/skills/typesafe-ai/SKILL.md  
- Teaches System One (state + questions, fan-out, confidence). **Does not install remember-me.**

### Hooks (evidence)

Claude Code hooks reference: https://code.claude.com/docs/en/hooks  

Relevant events for a future remember-me adapter:

| Event | Possible use |
|-------|----------------|
| `UserPromptSubmit` | Inject hydrated stubs/context before the turn (additionalContext) |
| `PreCompact` / `PostCompact` | Compaction community already uses this class of hooks (fast-jev) |
| `SessionStart` | Load durable prefs once |
| `PreToolUse` | Unrelated to memory hydrate; used for safety gates elsewhere |

fast-jev-compaction pattern: plugin hooks on compact path → Jev scores tool units → drop/truncate → fallback to built-in summary. That is **orthogonal** to remember-me’s retrieve→gate→hydrate.

### How remember-me would plug (honest)

1. **Library path (works conceptually today):** Python/subprocess or MCP wrapping `MemoryPipeline.run(query)` → return hydrated nodes as `additionalContext`.
2. **Skill path (not shipped):** Author `skills/remember-me/SKILL.md` describing when to call the CLI/library; install via Claude plugin or copy to `~/.claude/skills/`.
3. **Not drop-in:** No auto-hydrate of Claude’s own memory; no replacement for CLAUDE.md / project memory.

**Auto-intercept strength:** High *potential* via hooks; **zero** remember-me intercept shipped.

---

## Codex

### Agent Skills path (evidence)

- OpenAI docs: https://developers.openai.com/codex/skills  
- Skill = directory with required `SKILL.md` (`name` + `description`).  
- Load locations include `$CWD/.agents/skills`, `$REPO_ROOT/.agents/skills`, `$HOME/.agents/skills`, `/etc/codex/skills`.  
- Invocation: explicit `$skill` / `/skills`, or **implicit** when task matches `description`.  
- `allow_implicit_invocation: false` in `agents/openai.yaml` disables implicit match.

### TypeSafe skill install (evidence)

```bash
npx skills add typesafe-ai/skills --skill typesafe-ai
# optionally: -a codex
```

Also documented for Cursor and “everything else” alongside Claude’s plugin path ([agent-skill](https://docs.typesafe.ai/agent-skill), [Flavio](https://flaviocopes.com/jev/)).

Skills CLI agent map (vercel-labs/skills): Codex → `.agents/skills/` / `~/.codex/skills/`.

### How remember-me would plug

1. Ship `remember-me/SKILL.md` instructing Codex to call `remember-me` CLI or Python API before answering preference/history questions.
2. Keep TypeSafe skill separate (API literacy) vs remember-me skill (hydrate gate workflow).
3. **Weaker auto-intercept than Claude:** no PreCompact-style lifecycle hooks in the Skills model; reliance on description matching + explicit `$remember-me`.

**Auto-intercept strength:** Medium (implicit skill) — **weaker than Claude hooks**.

---

## Hermes

### hermes-jev-compact vs topology hydrate

| | hermes-jev-compact | remember-me (intent) |
|--|--------------------|----------------------|
| Seam | `_prune_old_tool_results` on full compression | After local candidate retrieve |
| State | Whole transcript (abridged) | Redacted marker metadata |
| Questions | 2× Noul per tool unit | Choice hydrate_action + Score need + Noul still_matters |
| Failure | Fall back to **deterministic prune** | Fail-closed **skip** (no cloud-influenced open) |
| Config | `context.engine: jev` | N/A in Hermes today |

Evidence: https://pypi.org/project/hermes-jev-compact/ (v0.1.3 as of research; MIT; port of fast-jev-compaction).

Install sketch (upstream README):

```bash
hermes-python -m pip install hermes-jev-compact
hermes plugins enable hermes-jev-compact --no-allow-tool-override
# config: context.engine: jev + TYPESAFE_API_KEY
```

### SOUL.md is generic identity — not JustinSun / not memory

Evidence: https://hermes-agent.nousresearch.com/docs/guides/use-soul-with-hermes  

- Path: `~/.hermes/SOUL.md` (or `$HERMES_HOME/SOUL.md`) — **never** cwd-local as identity.  
- Slot #1 of system prompt: personality / tone / stylistic avoidances.  
- Separate from `MEMORY.md` / `USER.md` / project `AGENTS.md`.  
- **Not** a place to embed JustinSun-specific lore by default; starter is generic.  
- Changing SOUL.md does **not** enable Jev compaction or remember-me.

### How remember-me would plug

1. New Hermes plugin or memory-provider that calls remember-me before LLM turns (volatile memory block in prompt assembly).  
2. Do **not** overload hermes-jev-compact — different questions and failure semantics.  
3. Do **not** stuff hydrate policy into SOUL.md.

**Auto-intercept strength for compaction:** High *if* `context.engine: jev`. **For remember-me hydrate:** none today.

---

## Plug-in recommendation (minimal)

| Priority | Action | Host |
|----------|--------|------|
| 1 | Fix HttpJev → System One; prove live gate | All |
| 2 | Optional `skills/remember-me/SKILL.md` (when/how to call CLI) | Claude + Codex via skills ecosystem |
| 3 | Optional Claude `UserPromptSubmit` hook wrapping pipeline | Claude only |
| 4 | Do **not** claim overlap with hermes-jev-compact metrics | Hermes |
| 5 | Keep Jev off TEMPR ranking forever | Architecture freeze |

---

## Evidence link index

| Topic | URL |
|-------|-----|
| TypeSafe agent skill install | https://docs.typesafe.ai/agent-skill |
| typesafe-ai SKILL.md (raw) | https://raw.githubusercontent.com/typesafe-ai/skills/main/skills/typesafe-ai/SKILL.md |
| Jev primitives deep dive | https://flaviocopes.com/jev/ |
| Cloudflare Workers AI Jev | https://developers.cloudflare.com/ai/models/typesafe/jev/ |
| Vercel AI SDK + confidence floors | https://vercel.com/kb/guide/typesafe-jev-and-ai-sdk |
| Codex Agent Skills | https://developers.openai.com/codex/skills |
| vercel-labs/skills CLI | https://github.com/vercel-labs/skills |
| Claude Code hooks | https://code.claude.com/docs/en/hooks |
| hermes-jev-compact | https://pypi.org/project/hermes-jev-compact/ |
| Hermes SOUL.md | https://hermes-agent.nousresearch.com/docs/guides/use-soul-with-hermes |
| LiteLLM Jev compaction | https://docs.litellm.ai/blog/typesafe-jev-compaction |
| remember-me public repo | https://github.com/leonininder/remember-me |

---

## Wiki note

Leon’s Mac wiki (`~/OneDrive/Documents/Leon_LLM_Wiki`, jev_* / Pre_Skill topology markers) was **not** reachable from this research box (no ListMachines / machine bridge). Cross-check against wiki remains **TODO on Mac**.
