# Threat model — audit export (`audit_export`)

`audit_export` takes the append-only governed record **out of the product**: a
redacted, account-scoped JSONL file plus a manifest that names exactly which
events it covers and hashes that scope.

It exists because evidence that cannot leave is not evidence. A review, an
incident write-up, or a second tool cannot read the record through Raiker's own
screens, and until this capability had an executor the code that built the
manifest could not be reached at all — `audit_export` was one of the capabilities
listed in `ALL_CAPABILITIES` with no executor, so the gate could not be turned on
and no route surfaced the manifest.

## What the capability does

`raiker/runtime/executors/tier1_audit.py` → `AuditExportExecutor` calls
`raiker.events.export.generate_export`, which:

1. reads the event index for the scope (optionally one session or one project);
2. re-reads each event from its JSONL offset;
3. applies `redact_event_payload` to every payload;
4. writes the result to `.raiker/exports/<export_id>.jsonl` inside the
   workspace; and
5. records an `ExportManifest` row — export id, event count, first/last event id
   and timestamp, redaction flag, and a SHA-256 over the exact event ids and the
   scope.

The manifest hash is what makes the file usable as evidence: a reader outside
Raiker can say whether the file they were handed is the one Raiker produced, and
which events it claims to contain.

## Reachability

| Question | Answer |
|---|---|
| Has a real executor? | **Yes** — registered in `REAL_EXECUTOR_CAPABILITIES` |
| Reachable by a **model**? | **No.** There is no tool for it in `TOOL_DEFINITIONS`; an export is an owner action only |
| Reachable by the owner? | **Yes** — `POST /api/audit/export` (Observability → Audit log → Export), through `RuntimeControlService.export_audit_log` |
| Executed on approval? | **No** — and it does not need to be. It is not in `EXECUTABLE_ON_APPROVAL`; the owner performs it directly, governed |
| Audited? | **Yes.** It enters through `route_action`, so the export is an event in the log it exported |

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| An export widening who can read a record | Scope is the **acting principal's** `delegated_by_user_id`, read from the `Principal` inside the executor. It is never an argument, so a caller cannot name another account | `tier1_audit.py` |
| A secret riding out in a payload | Every payload passes `redact_event_payload` — the same redaction the on-screen record passes — before it is written. `redact=True` is not caller-controllable on this path | `raiker/events/export.py` |
| A model exfiltrating the record | No tool exposes this capability; the model cannot propose an export | `raiker/models/tool_registry.py` |
| The export disagreeing with the screen it was taken from | The visibility rule in `list_event_index` is the same one `DashboardService.list_events` applies: this account's own sessions, **or** no session record at all | `raiker/storage/sqlite.py` |
| A stored path addressing a file outside the workspace | The download route ignores the stored path string and re-resolves `<exports>/<export_id>.jsonl`, refusing anything whose parent is not the exports directory | `raiker/api/routes_control.py` |
| An automation exporting unattended | `export_audit_log` refuses a non-human principal with `not_authorized_human` | `raiker/control/service.py` |
| An export happening with the gate closed | The action passes the `audit_export` capability gate before any executor runs; a closed gate returns `disabled_by_capability_gate` | `RuntimeAuthority.route_action` |

## Residual risk, stated plainly

* **A redacted export is still the record.** Redaction removes secret-shaped
  values, not meaning: an export names sessions, tools, capabilities, hosts and
  timestamps. Handing one to a third party discloses how the owner works.
  Nothing here prevents that, and nothing should — it is the owner's record and
  the owner's decision.
* **The file lives in the workspace.** `.raiker/exports/` is inside the
  workspace like every other Raiker artefact, so anything with read access to
  the workspace can read a produced export. Producing one is audited; reading
  the resulting file afterwards is not.
* **Bounded at 10 000 events.** `generate_export` reads at most that many rows,
  newest first. A longer history exports its most recent window rather than
  failing, and the manifest states the window honestly (`first_timestamp` /
  `last_timestamp`) rather than implying completeness.
