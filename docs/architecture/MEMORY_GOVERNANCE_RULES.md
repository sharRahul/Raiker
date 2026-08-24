# Memory governance

Durable memory is governed local state, not a model-owned scratchpad.
`/memory-store` and `/memory-forget` are brokered approval-required requests.
Secret/credential-like durable memory content is denied before approval
creation.

secret/credential-like durable memory content is denied before approval creation

Successful governed changes emit `memory_record_created` or
`memory_record_forgotten` audit events. Semantic/vector and broader autonomous
memory work remain policy-gated or fail closed when no applicable executor is
available. Memory reads never grant authority to execute other actions.
