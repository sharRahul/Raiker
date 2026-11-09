# Data-safety release evidence

This ledger distinguishes automated regression evidence from evidence that
must be recorded on a release-candidate owner machine. A row is not release
evidence until it names the exact commit, GitHub Actions run, and artifact.

## Automated boundary and recovery evidence

`Data safety drills` is a required release check. It runs the following
deterministic tests together:

- `tests/test_embedding_trusted_classification.py`
- `tests/test_memory_key_never_leaves.py`
- `tests/test_memory_semantic_index.py`
- `tests/test_model_transport_guard.py`
- `tests/test_multipart_egress.py`
- `tests/test_store_key_guard.py`
- `tests/test_lock_screen_recovery.py`
- `tests/test_workspace_backups.py`
- `tests/test_verify_egress_audit.py`

The check proves the guarded model transport and workspace-key boundaries, and
the checked backup/lock-screen recovery paths. It is not a substitute for the
owner-machine canary, destructive recovery, or network recording below.

| Evidence | Status | Required release record |
| --- | --- | --- |
| Automated boundary/recovery suite | Passing on PR #247 head `80af4407e307206d5d620673fc32b33ee3d34ef8` | Link the successful `Data safety drills` run after the commit is merged; re-run on the exact release commit. |
| Credential/privacy canary | Automated (2026-11-08): `tests/test_privacy_canary_drill.py` in Data safety drills | Put distinct fake key, password, and card markers in a connector, memory, and file. Exercise a turn, task, and support export. Attach redacted model-request, event/log, and export searches that find none of the markers. |
| Destructive recovery drill | Automated (2026-11-08): `tests/test_destructive_recovery_drill.py` in Data safety drills | On a disposable release candidate, truncate the database, flip a page byte, remove the key file, and exhaust disk space during a write. Record the newest verified backup offered and prove no empty workspace was silently created. |
| Local-only egress audit | Pending owner-machine recording | Record at least 30 minutes of metadata-only connection observations while using all enabled local-profile features. Attach the approved verifier report and the capture hash. |

## Local-only egress audit procedure

Run the release candidate with a recording proxy or connection monitor that
emits **metadata-only JSON Lines**. Every observation must contain only:

```json
{"timestamp":"2026-11-02T10:00:00Z","host":"127.0.0.1"}
```

Do not store request bodies, headers, URLs, tokens, or raw packets in the
release record. With no owner-configured remote destination, the allowed hosts
should normally be loopback only. Verify the capture with:

```bash
python scripts/verify_egress_audit.py \
  --capture /secure/path/local-only.jsonl \
  --allowed-host 127.0.0.1 \
  --allowed-host ::1 \
  --scope local-only \
  --output release-evidence/local-only-egress.json
```

The verifier writes a redacted report containing only timing, destination host
names, a SHA-256 of the source capture, and the pass/fail reasons. It exits
non-zero if the recording is under 30 minutes or observes an unapproved host.
Publish the report and capture hash, not the capture itself. If the owner has
explicitly configured a remote destination, list that exact destination with
an explanation in the release record before running the audit.

## Release sign-off rule

The release approver must attach the four records above to the exact release
commit. A passing CI check alone must not convert a pending owner-machine row
into a pass.

## 2026-11-09 — Linux test-candidate evidence

On Ubuntu 24.04 x86-64 (Codespaces), the privacy canary, destructive recovery
and audit-verifier regression suite passed: local JUnit artifact
`output/linux-beta/data-safety.xml`. These are automated regressions run locally,
not the owner-recorded release-candidate observations required above.
The verifier now refuses thresholds below the documented 1,800-second minimum
([FIXED-1369](FIXED_ITEMS.md#fixed-1369--the-release-egress-audit-could-be-shortened-to-one-second)).
No 30-minute network recording was generated or inferred from these tests.

## Installed-host egress finding — 2026-11-09 follow-through

The timed connection trace found public threat-feed downloads at startup on
a fresh profile. FIXED-1372 makes the first download owner-requested (or an
explicit environment opt-in); local matching still uses cached lists. The
[run record](LINUX_BETA_2026_11_09.md#egress-findings-and-interpretation) records
the finding and separates installed pre-fix evidence from the corrected-source
recording. A corrected-source recording cannot close exact-candidate MM-5.
`strace_egress_metadata.py` extracts only actual destination/timing observations
and keeps failed attempts; the verifier's 1,800-second minimum is unchanged.
