# Threat Model - Vector Embedding Runtime (Tier 3, local-only)

`vector_embedding_runtime` is promoted to a real executor because it can produce
a genuine embedding **entirely locally** — no embedding-model download, no
network call, no external service. It computes a deterministic embedding with the
hashing trick (`raiker.vector.embed_text`) and persists a `vector_records` row.
The provider-backed sibling `model_provider_runtime` (learned semantic embeddings
or generation through an LLM provider) stays **fail-closed** until its own
egress-gated slice lands.

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
- Supported `action` values are `embed` (default) and `list`; anything else fails
  closed with `unknown_action:<op>`.
- `embed` requires a non-empty `text` (`missing_argument:text`), caps text length
  at 20000 chars (`text_too_long`), and validates optional `scope`/`sensitivity`
  types (`invalid_argument:scope_or_sensitivity`). It writes a single row to the
  local `vector_records` table.
- **No network, no model download.** The executor imports no ML framework, opens
  no socket, and fetches no weights. The embedding is pure Python over the input
  string.
- **Metadata-only artifacts.** Runtime artifacts contain ids/model/dims/hash only
  (`vector_id`, `embedding_model`, `dimensions`, `content_hash`,
  `content_redacted=true`, and for `list`: `count`, `vector_ids`) — the source
  text is never emitted into runtime events. A bounded 120-char preview is stored
  in the local table only (mirrors how reminder titles are stored locally).

## Explicit non-goals

- No provider/API embedding call (that is `model_provider_runtime`, egress-gated).
- No semantic/neural embedding quality — lexical hashing only.
- No similarity **search** here — retrieval is `semantic_memory_runtime`'s job.
  This slice only creates and lists embedding records.
- No deletion/update of vector records in this slice (embed + list only).

## Acceptance evidence

- `tests/test_phase_6_vector_embedding_runtime.py` proves deterministic/normalized
  embeddings, default-disabled blocking, embed-writes-a-real-vector-row,
  missing-text fail-closed, unknown-action fail-closed, list-returns-count, and
  that source text never appears in runtime event payloads.
- `tests/test_executor_default_registry.py` proves `vector_embedding_runtime` is
  in `REAL_EXECUTOR_CAPABILITIES` while `model_provider_runtime` is not.
