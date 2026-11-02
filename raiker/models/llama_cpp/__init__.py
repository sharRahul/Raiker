"""The llama.cpp engine Raiker installs, sizes, starts and watches for the owner.

Before this package Raiker could *serve* a GGUF model only when the owner had
already put a ``llama-server`` on ``PATH`` and accepted the server's defaults: no
GPU offload unless they knew the flag, the model's full trained context whether
or not it fitted, and nothing that noticed the server dying. The modules here
close those gaps, each answering one question:

* :mod:`.hardware` — what this machine has: memory, GPUs and their memory, and
  which llama.cpp backend (CUDA, Vulkan, Metal or CPU) suits it.
* :mod:`.releases` — which official ggml-org release asset is that backend's,
  for this operating system and architecture.
* :mod:`.installer` — downloading that asset, proving it is the published
  bytes (the release's SHA-256 digest), unpacking it safely and recording it.
* :mod:`.planner` — how many layers to offload, how much context to allocate,
  and whether the result fits in memory at all before anything is started.
* :mod:`.supervisor` — health checks, restart with backoff, recovery from an
  out-of-memory start, restoring deployments when Raiker starts, and stopping
  every server when it exits.
"""
