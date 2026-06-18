# Phase 5 Build Plan — Governed Enterprise and Home-Lab Platform

Phase 5 adds managed governance, hosted/cloud operations, marketplace/supply-chain controls, audit export, policy dashboards, budget controls, encrypted/retained storage options, and organization/home-lab administration.

Phase 5 must not be used to bypass earlier phase gates. It builds on the safe metadata, policy, approval, storage, and validation foundations created in Phases 1 through 4.

---

## Dependency Graph

```text
RAIKER-5001 managed policy model
  -> RAIKER-5101 organization/home-lab roles and access
  -> RAIKER-5201 enterprise audit export and event integrity
  -> RAIKER-5301 plugin marketplace and signed trust pipeline
  -> RAIKER-5401 hosted routines, notifications, and share links
  -> RAIKER-5501 cloud/GPU execution budget controls
  -> RAIKER-5601 retention, archive, and backup/restore governance
```

---

## Tasks

| Task ID | Scope | Contracts/events/storage | Policy | Tests | Acceptance criteria |
|---|---|---|---|---|---|
| RAIKER-5001 | Managed policy model | Managed policy records and override events | Managed deny wins over project/user/plugin policy | Policy override tests | Managed policy cannot be bypassed by clients, tools, hooks, plugins, or channels. |
| RAIKER-5101 | Organization/home-lab roles | User/role/session records | RBAC and least privilege | Role boundary tests | Users can only access permitted sessions, projects, tools, and exports. |
| RAIKER-5201 | Audit export and event integrity | Audit export manifests and hash-chain metadata | Export approval and tamper checks | Export/integrity tests | Audit exports are complete, redacted, and verifiable. |
| RAIKER-5301 | Plugin marketplace and signed trust | Registry, checksum, signature, permission diff records | Supply-chain approval | Marketplace trust tests | Marketplace install/update cannot activate code without signed trust and policy. |
| RAIKER-5401 | Hosted routines, notifications, and share links | Hosted routine records, push/link events | Privacy/auth/expiry controls | Hosted privacy tests | Hosted push/share links require explicit policy, auth, and expiry. |
| RAIKER-5501 | Cloud/GPU execution | Budget, job, artifact, cost records | Budget and egress policy | Budget denial tests | Cloud jobs cannot exceed configured budget or egress policy. |
| RAIKER-5601 | Retention/archive/backup | Retention, legal hold, backup manifests | Managed retention policy | Retention/restore tests | Cleanup respects legal holds and preserves required audit records. |

---

## Phase 3 Slice G dependency boundary for Phase 5 builders

Phase 5 builders must treat `docs/PHASE_3_SLICE_G_STORAGE_LIFECYCLE_SPEC.md` as a prerequisite for any work that persists lifecycle metadata, exports lifecycle metadata, links lifecycle metadata to hosted routines, or includes lifecycle records in audit reports.

Slice G lifecycle records are metadata-only. Phase 5 may add managed retention, archive, export, and hosted governance around those metadata records, but it must not retroactively convert them into executable storage jobs.

Allowed Phase 5 interactions with Slice G metadata:

- managed retention policies for lifecycle metadata;
- audit export of redacted lifecycle summaries;
- integrity hashing of lifecycle metadata events;
- dashboard reporting over lifecycle counts/statuses;
- backup/restore of metadata-only lifecycle tables;
- managed policy that keeps lifecycle execution disabled.

Forbidden Phase 5 interactions until a later explicit implementation task exists:

- graph/codemap runtime indexing from lifecycle records;
- semantic/vector memory writes from lifecycle records;
- embedding generation from lifecycle records;
- rollback execution from lifecycle records;
- hosted routine execution based only on lifecycle status;
- marketplace plugin execution based on lifecycle status;
- cloud/GPU job execution based on lifecycle status.

---

## Storage requirements

Phase 5 may extend storage for enterprise/home-lab governance only after schemas, migrations, redaction, retention, and tests are documented.

Allowed Phase 5 storage categories:

- managed policies;
- users/roles/access grants;
- audit export manifests;
- event integrity hashes;
- plugin marketplace provenance;
- hosted routine metadata;
- notification/share-link metadata;
- budget/cost records;
- backup/restore manifests;
- retention/legal-hold records;
- lifecycle metadata archive indexes.

Forbidden without a specific later task:

- active graph node/edge write paths;
- vector/embedding tables that are populated automatically;
- unredacted lifecycle payload exports;
- unmanaged hosted execution tables;
- marketplace tables that imply plugin code activation without trust review.

---

## Validation requirements

Every Phase 5 PR must include local/cloud validation evidence.

Required minimum commands while GitHub Actions remain paused:

```bash
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
python -m apps.cli.main --help
python -m apps.cli.main --prompt "Hello Raiker"
```

Additional Phase 5 tests must prove:

- managed deny overrides user/project/plugin allow;
- audit export redacts lifecycle metadata;
- lifecycle metadata export includes counts and source IDs but not unsafe payloads;
- hosted routines cannot execute lifecycle records;
- marketplace plugins cannot activate lifecycle execution;
- budget controls deny cloud execution by default;
- retention cleanup preserves legal holds and audit requirements.

---

## Completion rule

Phase 5 is not complete until governance, managed policy, audit export, marketplace trust, hosted privacy/auth, cloud budget controls, retention/archive, backup/restore, tests, and CI evidence are all present.

A builder must not mark Phase 5 complete because a metadata table, dashboard summary, or hosted config exists. Runtime authority requires explicit policy, approval, event logging, redaction, rollback planning, and verification.
