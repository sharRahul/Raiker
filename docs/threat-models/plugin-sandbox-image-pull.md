# Threat Model - Sandboxed Plugin Image Pull (Tier 4)

`plugin_sandbox_image_pull_cap` acquires an image for
`plugin_sandboxed_runtime_cap`. It pulls an owner-approved exact image reference;
it does not build an image, run an image, or load plugin code.

## Boundaries enforced

- The capability defaults disabled. Enabling requires a human runtime gate
  manager, `local_single_user_runtime`, this threat-model acknowledgement, and a
  confirmation token.
- `image` must be a non-empty string and exactly match
  `RAIKER_CONTAINER_IMAGE_ALLOWLIST`. An empty image allowlist denies all pulls.
- The reference's registry must exactly match
  `RAIKER_PLUGIN_IMAGE_REGISTRY_ALLOWLIST`; an empty registry allowlist denies
  all pulls. References without an explicit registry are treated as `docker.io`.
- The only spawned argv is `docker pull <exact-image-reference>`. No shell,
  Dockerfile, build context, archive, extra argument, plugin entrypoint, or
  container execution is accepted.
- Pulls are bounded to 300 seconds and 200 KB of captured output. Artifacts and
  events carry only reference/registry, exit status, byte counts, and truncation;
  Docker output and registry credentials are never exposed.
- Missing Docker fails closed as `docker_unavailable`; a non-zero pull becomes
  `plugin_image_pull_exit:<code>`.

## Explicit non-goals and operator boundary

- No image build, tag mutation, dependency installation, package download,
  plugin installation, or plugin execution.
- No digest inspection or persistence. The owner must provide an exact allowed
  reference; digest pinning is a future supply-chain hardening slice.
- Docker's daemon, not Raiker, performs registry networking. Raiker verifies
  the registry name before calling Docker but cannot firewall daemon mirrors,
  token services, or registry egress. Operators who need that boundary must
  configure Docker/host network policy separately.

## Acceptance evidence

`tests/test_phase_4_plugin_image_pull.py` covers registration, disabled gate,
both owner allowlists, registry mismatch, exact Docker argv, output redaction,
missing Docker, and non-zero exits.
