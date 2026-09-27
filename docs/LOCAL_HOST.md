# Local context host

Turn a trusted JSON memory file into messages your Python agent can consume, with explicit scope admission and a byte limit. This adapter runs locally and uses **deterministic scope rules**, not FakeJev, TypeSafe, or an LLM. It does not answer the final question or call a model.

```sh
python -m remember_me.local_host --memories examples/host_memories.json --scope alpha --query build --max-bytes 256
```

The example returns the Alpha build command as a memory message. It excludes the Beta build command, holds the pending Alpha change for review, and skips unscoped memories. The output includes `messages` and a separate `audit` record with included/review/omitted IDs. Send `messages` to your own model adapter only after applying your application's authorization policy.

Condensed output from the command above (timing, message text and other audit fields omitted):

```json
{"audit":{"included_ids":["alpha_build"],"review_ids":["alpha_review"],"budget_omitted_ids":[],"context_bytes":74,"max_bytes":256}}
```

The raw JSON also records skip decisions for `beta_build` and `unscoped_build`; an escalation is not an automatic message to a person.

## Supply your memories

The input is a JSON array of unique IDs, text, and string tags:

```json
[{"id":"build_command","text":"Build with python -m build.","tags":["scope:alpha","build"]}]
```

The host retrieves keyword matches in the existing local ranking order. A candidate is admitted only when it has exactly one matching `scope:<name>` tag and no `private` tag. A `review` tag produces an escalation record instead of context. Unknown or ambiguous scopes are skipped. This is a simple application policy; it does not understand arbitrary semantic relevance. Broad queries can still retrieve irrelevant same-scope memories.

Use trusted files and select the scope in trusted application code. Tags are **not authentication**: an attacker who can edit the file can forge them. Do not use this as a multi-tenant security boundary. Memory text remains untrusted data; the instruction in the message is guidance, not a prompt-injection guarantee.

## Budget and output contract

- `--max-bytes` caps the UTF-8 encoded JSON memory block, including IDs and separators. Whole memories are admitted in retrieval order; oversized records are omitted, never silently truncated.
- This is a **byte budget**, not a token budget. System instructions, the `Memory records (JSON):` wrapper, and the user query are outside this limit. Account for those separately in a model's context window.
- `--top-k` limits retrieved candidates before scope admission. Other-scope matches can crowd out valid ones; review `candidate_ids` when diagnosing a miss.
- The audit omits bodies and uses SHA-256 for the query. IDs may still be sensitive, and hashes can permit guessing; protect logs accordingly.
- The host performs no durable writes, model request, or automatic human notification. `review_ids` must be routed by your application.

Python integration:

```python
from pathlib import Path
from remember_me.local_host import assemble_context, load_graph

result = assemble_context(load_graph(Path("examples/host_memories.json")),
                          "build", scope="alpha", max_bytes=256)
messages = result["messages"]
# Pass messages to your own authorized model adapter, or inspect them locally.
```

## Reproduce the comparison

```sh
python examples/evaluate_local_host.py
```

This compares dump-all, local top-k, and scoped admission on the **same six hand-authored tasks and seven synthetic memories**, with the same 2,048-byte memory cap. Each case runs 20 times and records included IDs, retained/missed expected memories, wrongly included memories, byte use, and local elapsed time. The baselines intentionally lack scope admission; the result measures the value of that explicit rule, not superiority over a scope-aware memory product.

This is an executable policy and integration check. It is not independent user validation, learned relevance quality, production latency, an LLM-answer evaluation, or evidence about the TypeSafe service. No live API credentials are required.

## Chinese and unsupported queries

The local retriever now tokenizes Unicode words and overlapping CJK bigrams. For example, `建置指令` can match that phrase inside a longer Chinese memory; accented words retain their accents. This is lexical matching, not a Chinese language model or semantic search. It does not infer synonyms or convert Traditional/Simplified Chinese.

The host rejects blank queries and input with no searchable tokens (such as only emoji, punctuation, or a single Latin letter). It never turns those inputs into a recency dump. The low-level retriever preserves an explicit empty-string recency view for existing callers, while non-empty untokenizable input returns no candidates.
