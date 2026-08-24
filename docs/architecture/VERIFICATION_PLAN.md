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

## The documentation tests in `pytest`

`tests/test_docs_consistency.py` runs in the ordinary suite, so these are gates
CI already enforces rather than a separate step. Each exists because the thing it
asserts had actually broken:

| Test | What it asserts |
|---|---|
| `test_required_docs_do_not_contain_stale_model_runtime_claims` | Eleven documents do not carry any of the retired model-runtime claims |
| `test_every_real_executor_capability_has_a_threat_model` | Every name in `REAL_EXECUTOR_CAPABILITIES` appears in `docs/threat-models/README.md`. The step-up asks the owner to acknowledge a threat model; this is what stops a capability gaining an executor without one |
| `test_documentation_links_and_anchors_resolve` | Every relative Markdown link in `README.md`, `docs/**` and `apps/web/README.md` resolves — **including its heading anchor**, using GitHub's slug algorithm |
| `test_relayed_capability_count_is_stated_correctly` | `EXECUTABLE_ON_APPROVAL` still has twelve members, and `README.md` still says so. Changing the set without updating the documents that name the number fails here |

`tests/test_governance_entry_paths.py` asserts the enumeration in
[`plans/GOVERNANCE_ENTRY_PATHS.md`](../plans/GOVERNANCE_ENTRY_PATHS.md), because a
document describing every way an action reaches an executor fails **silently**:
a new path appears beside the governed ones and nothing breaks.

| Test | What it asserts |
|---|---|
| `test_i1_route_action_callers_are_the_enumerated_ones` | `RuntimeAuthority.route_action` is called from exactly the five modules the document names. A sixth is a new entry into the governed chokepoint |
| `test_i2_agent_gateway_is_constructed_only_by_enumerated_surfaces` | `AgentGateway` is constructed only by the four surfaces named. This is what makes "every interface enters through the Agent Gateway" checkable |
| `test_i3_every_real_executor_capability_is_named_in_the_enumeration` | Every capability with a real executor is named in the enumeration with the path that reaches it. A new registered executor cannot appear without someone writing down how it is reached — the step nobody took for `network_execution` before it was deleted (BUG-232) |
| `test_i3b_the_tool_reachable_set_is_exactly_sixteen` | Sixteen capabilities are reachable by a model tool through `CAPABILITY_GATE_MAP`. A change moves a capability between reachability categories |
| `test_i4_local_gate_checks_are_the_enumerated_ones` | Every module that reads a capability gate directly calls the one shared `capability_admission` helper and is enumerated. A further one cannot appear silently |
| `test_i4b_no_module_carries_its_own_copy_of_the_gate_lookup` | No module outside `admission.py` declares its own enabled-state set. The original I4 watched for a *marker* rather than the behaviour, and missed a module that spelled the constant differently |
| `test_i5_a_hook_can_never_grant` | `combine()` returns only `deny`, `ask` or `no_decision` for every scope, decision and authority combination — an `allow` can never override a `deny` |
| `test_every_real_executor_capability_is_classified` | Every capability with a real executor says whether its own gate decides anything, or what does instead. A registered executor cannot ship without an answer (GEP-04) |
| `test_model_tool_entries_match_the_tool_registry`, `test_approval_relay_entries_match_the_relayable_set` | The entry-path table's claims are checked against `TOOL_DEFINITIONS` and `EXECUTABLE_ON_APPROVAL` rather than trusted |

## What is not automated

- **External URL checking.** Internal links and anchors are now asserted by
  `test_documentation_links_and_anchors_resolve` (see above), which closes the
  item that stood here. **External** URLs are not fetched by CI — that would
  make the build depend on other people's uptime and on hosts that refuse
  automated requests. They are re-read by hand each reconciliation, and the
  result is recorded per domain in
  [`REFERENCE_PLATFORM_COMPATIBILITY.md` §1](REFERENCE_PLATFORM_COMPATIBILITY.md#1-reference-platforms-and-sources)
  rather than assumed.
- **The `live` end-to-end suite.** It needs real provider credentials; see
  [LOCAL_VALIDATION_GATE.md](LOCAL_VALIDATION_GATE.md).
- **The manual browser round.**
  [`plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md`](../plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md).
