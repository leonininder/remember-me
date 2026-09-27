# remember-me release candidate and feedback

Candidate: **local context host / 2026-09-27**, based on `55108ed5c1cea2211b406ab98ba731d5247c7a83` plus the reviewed working-tree changes. This is an unpublished candidate, not a tag or a live release. Freeze its final commit and archive its diff before publication; never present the base SHA as including these changes.

## Candidate release notes

- Executable local context assembly from a trusted JSON file: keyword retrieval, scope/private/review decisions, explicit byte cap and body-free decision audit.
- Unicode/CJK lexical retrieval; blank/unsupported host queries fail explicitly.
- Closed HTTP answer schemas reject malformed values/types and preserve IDs containing `__`; real loopback tests exercise the wire boundary.
- Stage-only write admission cannot commit memory; empty supplied graphs retain object identity. Dual decisions use a query hash rather than a query prefix.
- Revised setup and limitations; no new model, automatic chat-host installation, semantic ranking improvement or external user claim.

## Reproduce before publishing

Use the [README setup](../README.md#quick-start), then run from the repository root:

```sh
python -m pytest -q
python -m ruff check .
python -m remember_me.local_host --memories examples/host_memories.json --scope alpha --query build --max-bytes 256
python examples/evaluate_local_host.py
```

Recorded on native Windows with Python 3.13: 268 tests passed, Ruff passed. The host includes `alpha_build`, holds `alpha_review`, and emits 74 context bytes. The synthetic comparison retained all four expected memories and admitted zero wrong memories under its explicit scope rules. It is not a competitor benchmark, learned relevance evaluation or production latency claim. See [host contracts](LOCAL_HOST.md).

No hosted API call is required for these commands. Python dependencies require installation/network unless cached; there is no model download. Installation time, Linux/macOS fresh installation and live TypeSafe availability were not measured in this candidate. Historical live evidence stays separate in the README.

Publication checklist (unchecked means pending, not failure):

- [ ] Record final candidate commit, diff hash, Python/OS and exact test output in the release receipt.
- [ ] Re-run the commands above on that commit; inspect the packaged examples/docs and README links.
- [ ] Inspect the diff for secrets/private text and retain LICENSE/SECURITY boundaries.
- [ ] Publish repository changes and verify the links from a logged-out view before sharing a candidate link.
- [ ] Apply truthful About/topics below; record timestamp and release URL (or explicitly no GitHub Release).
- [ ] Recheck the destination's current rules and thread before posting the draft once.
- [ ] Record real feedback separately; update issue/release notes for reproducible defects. Revert the release commit if a blocking regression is confirmed.

## About and topics candidate

About: **Gate which local agent memories reach the prompt, with explicit inclusion decisions, write checks, and audit records.**

Topics: `python`, `agent-memory`, `llm-agents`, `context-management`, `local-first`, `decision-gate`. These are proposed settings, not a claim they have been applied online.

## Specific sharing route and draft

Audience: Python developers assembling local agent context. The [r/Python monthly Showcase thread](https://www.reddit.com/r/Python/comments/1w78kp5/showcase_thread/) explicitly accepts project showcases; its opening instruction was checked 2026-09-27. It recycles monthly. Check the [current rules](https://www.reddit.com/r/Python/about/rules) and newest pinned Showcase before posting. Use a reply in that thread rather than assume a standalone promotional post is welcome. No post or outreach is performed by this document.

Ready-to-edit draft (publish only after the code link resolves to the candidate):

> **What My Project Does**
>
> I maintain remember-me, an experimental Python memory gate. Given a local JSON memory file, the new context host emits agent messages plus an audit showing what was included, skipped or held for review. In the checked example, querying “build” in scope Alpha includes Alpha's command, excludes Beta's command and holds a pending change. It runs without an API key. Scope tags must come from trusted application code: this is not authentication, semantic search or prompt-injection protection. There are runnable examples and real localhost HTTP failure tests. Repo: https://github.com/leonininder/remember-me .
>
> **Target Audience**
>
> Python developers assembling agent prompts from trusted local memory files. Can you reproduce the example and report the first unclear or failing step? The issue templates ask for a synthetic reproduction; please omit private memories and credentials.
>
> **Comparison**
>
> Dump-all context admits every stored item; a local top-k retriever ranks matches. This host adds an explicit scope admission step and audit after retrieval. Its synthetic scope-rule comparison is not evidence of superiority over scope-aware tools or semantic memory products.

## Feedback and market record

Use the repository's **Bug report** or **First-run feedback** issue template. Do not require a star, favorable score or public disclosure of private logs. A useful report includes revision, OS/Python, command, expected and actual behavior, minimal synthetic data and whether the example completed.

| Observation | Actual value |
|---|---|
| Published candidate SHA / URL / date | Pending |
| Showcase permalink / posting date | Not posted |
| First-run attempts and successful completions | Not measured |
| First blocking step and elapsed setup time | Not measured |
| Repeat use / reason for not reusing | Not measured |
| GitHub visitor / clone window | Not obtained; agent/maintainer clones contaminate counts |

Observe for 14 days after actual posting. Compare failures and completed attempts before interpreting stars. Visitor and clone counts are not a linked user funnel. No feedback means unknown demand, not a fabricated success or failure. Release readiness and these market observations are separate judgments.
