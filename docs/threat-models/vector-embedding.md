# Threat Model - Vector Embedding Runtime (Tier 3, local-only)

`vector_embedding_runtime` is promoted to a real executor because it can produce
a genuine embedding **entirely locally** — no embedding-model download, no
network call, no external service. It computes a deterministic embedding with the
hashing trick (`raiker.vector.embed_text`) and persists a `vector_records` row.
The provider-backed sibling `model_provider_runtime` (semantic embeddings through
an LLM provider) is a **separate, egress-gated executor** — see
[`model-provider.md`](model-provider.md).

## What the embedding is (honest scope)

- A **deterministic feature-hashing (bag-of-tokens) vector**, L2-normalized, of
  fixed dimension 384. Same input text → identical vector, on any machine, with
  no model weights.
- It captures **lexical overlap**, not learned semantics. It is a legitimate
  baseline embedding (comparable to a `HashingVectorizer`), not a neural
  sentence embedding. Callers must not treat similarity as semantic
  understanding. A semantic model-backed path is deliberately a separate slice.

## Boundaries enforced (fail-closed)

- Gate defaults disabled. Enabling requires a HUMAN `runtime_gate_manager`,
  `local_single_user_runtime`, and a confirmation token (the capability is in the
  dangerous-caps set). AI-proposed actions are further governed by the capability
  decision mode (default `ask`).
- Supported `action` values are `embed` (default), `list`, and `search`; anything
  else fails closed with `unknown_action:<op>`.
- `embed` requires a non-empty `text` (`missing_argument:text`), caps text length
  at 20000 chars (`text_too_long`), and validates optional `scope`/`sensitivity`
  types (`invalid_argument:scope_or_sensitivity`). It writes a single row to the
  local `vector_records` table.
- `search` requires a non-empty `query` (`missing_argument:query`), caps its length
  at 20000 chars (`query_too_long`), and validates `top_k` (1–100 integer,
  `invalid_argument:top_k`) and optional `scope` (`invalid_argument:scope`). It
  embeds the query with the **same local model**, then ranks by cosine similarity
  over stored vectors of that model only (`raiker.vector.VectorIndex`). Read-only:
  it writes nothing.
- **No network, no model download.** The executor imports no ML framework, opens
  no socket, and fetches no weights. Both embedding and search are pure Python over
  the input string(s).
- **Metadata-only artifacts.** Runtime artifacts contain ids/model/dims/hash/scores
  only (`vector_id`, `embedding_model`, `dimensions`, `content_hash`,
  `content_redacted=true`; for `list`: `count`, `vector_ids`; for `search`:
  `count` and `results` as `{vector_id, score}` pairs) — the source text, the
  query, and stored previews are never emitted into runtime events. A bounded
  120-char preview is stored in the local table only (mirrors how reminder titles
  are stored locally).

## Explicit non-goals

- No provider/API embedding call (that is `model_provider_runtime`, egress-gated).
- No semantic/neural embedding quality — lexical hashing only, so `search` ranks
  by lexical overlap, not meaning.
- `search` only retrieves within the **local hashing-embedding space**; it never
  ranks provider-model vectors (cosine across different embedding spaces is
  meaningless) and never returns document content — only ranked ids + scores.
  Fetching the underlying content is a separate governed read, out of scope here.
  This is distinct from `semantic_memory_runtime`, which searches the memory store.
- No deletion/update of vector records in this slice (embed + list + search only).

## Acceptance evidence

- `tests/test_phase_6_vector_embedding_runtime.py` proves deterministic/normalized
  embeddings, default-disabled blocking, embed-writes-a-real-vector-row,
  missing-text fail-closed, unknown-action fail-closed, list-returns-count, and
  that source text never appears in runtime event payloads. For `search` it proves
  exact-match ranks first (cosine ~1.0) without leaking the query, `top_k` is
  honored, other embedding models are excluded, an empty corpus returns `count=0`,
  and missing-query / invalid-`top_k` fail closed.
- `tests/test_executor_default_registry.py` proves `vector_embedding_runtime` is
  in `REAL_EXECUTOR_CAPABILITIES` while the sensitive/no-executor domains are not.
