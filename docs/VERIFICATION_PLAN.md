# Verification plan

What CI runs, and what to run before pushing. Where this document and
`.github/workflows/` disagree, the workflows win and this document must be
updated.

## What CI runs

Four workflows run on a pull request and on a push to `main`; a fifth is
`workflow_dispatch` only.

### `ci.yml` — the main gate

| Job | What it does |
|---|---|
| **Python 3.11** | Installs the package with `[dev]`; asserts a real `httpx` import; **asserts the SQLCipher build provides FTS5**, because a wheel that lost it would silently drop both text indexes to FTS4 and recency ordering with every test still passing; **asserts the SQLCipher memory-security probe** on the Linux host; runs the full pytest suite with `RAIKER_SQLCIPHER_MEMORY_SECURITY=off`; re-runs `tests/test_sqlcipher_memory_security.py` and `tests/test_memory_sqlcipher.py` **without** that job-wide override, in the same process a contributor uses, because `cipher_memory_security` is a process-global one-way latch and the override made the gate blind to an ordering defect (BUG-205); then Ruff, mypy over `raiker apps tests`, and `compileall`. |
| **Native runner (`ubuntu-latest`, `windows-latest`)** | `cargo fmt --check`, `cargo clippy --all-targets -D warnings`, `cargo test --all`, then `scripts/build_native_runner.py`. The sandbox runner is the only non-Python part of Raiker and the part that builds the operating-system boundary; a boundary that compiles on one machine is not a boundary. |

### `licensing.yml`

Validates licences and generates an SPDX SBOM
(`scripts/licensing_check.py --sbom`), then builds the distributions and
validates them (`--dist-dir dist`). Web dependencies are installed from the
lockfile with `npm ci`.

### `phase-status.yml`

`scripts/validate_phase_status.py` — asserts that `README.md` and four
documents exist and still contain the markers that make their status claims
falsifiable. **A documentation change that removes one of those phrases fails
CI**, which is deliberate: the phrases are the claims.

### `web.yml` — only when `apps/web/**` changes

Node 22: `npm ci`, lint, `check`, unit tests, build, then the **mocked**
end-to-end suite against that build. Every API call is answered from a fixture,
so it needs no credential and no network. The `live` project — which drives a
real host holding real provider keys — is deliberately not run in CI, because a
suite that cannot really pass must not report that it did.

### `release.yml` — `workflow_dispatch` only

Builds a reproducible payload per platform on that platform's own runner, proves
it rebuilds to the same bytes, runs an encrypted-database packaging test there,
builds the installer, and signs the channel index the updater verifies. It
**refuses to build without code-signing identities**; `signing: skip` produces
artifacts named `-unsigned` that the product itself calls unsigned and that the
publish job will not release.

## Required local checks

```powershell
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
python -m compileall -q raiker apps tests
python scripts/validate_phase_status.py
python scripts/validate_repo_truthfulness.py
python scripts/validate_documentation_truthfulness.py
python scripts/validate_runtime_enablement_readiness.py
python scripts/validate_local_single_user_runtime.py
```

For dashboard changes, also run the web lint, check, test, build and mocked
end-to-end commands in [LOCAL_VALIDATION_GATE.md](LOCAL_VALIDATION_GATE.md).

## What the five validators check

They are documentation gates, not code gates. Each exists because a specific
untrue sentence once shipped.

| Script | What it asserts |
|---|---|
| `validate_phase_status.py` | Five documents exist and contain the exact phrases that carry their status claims |
| `validate_documentation_truthfulness.py` | Eight documents each contain the governance terms they must not quietly drop — owner bootstrap, acting-principal, `runtime_gate_manager`, recovery, the approval execution relay |
| `validate_repo_truthfulness.py` | Command snippets in the docs name only commands the CLI really has, and capability statuses come from the canonical set |
| `validate_local_single_user_runtime.py` | The single-runtime status markers are present across the eleven documents that carry them |
| `validate_runtime_enablement_readiness.py` | The enforcement phrases — strict non-allow blocking, role revoke governed, capability gate per action — are present where they are claimed |

## What is not automated

- **Link checking.** There is no link-check step in CI. Internal links, anchors
  and repository paths were audited by hand during the 2026-08-23 documentation
  reconciliation, and external URLs were verified where the network allowed.
  Adding a link check is worth doing and is not yet done.
- **The `live` end-to-end suite.** It needs real provider credentials; see
  [LOCAL_VALIDATION_GATE.md](LOCAL_VALIDATION_GATE.md).
- **The manual browser round.**
  [`plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md`](plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md).
