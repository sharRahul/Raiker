# Project-Only Export Design

## Scope

Add a human-initiated download of a project's existing redacted audit timeline.
The export includes only events belonging to sessions directly assigned to the
requested project. It does not include child projects, attachments, project
memory, filesystem contents, credentials, or scheduled work.

## Design

Reuse `raiker.events.export.generate_export` rather than creating a second
export format. Extend its event lookup with an optional `project_id` filter;
the SQLite query resolves project membership through `sessions.project_id`.
The manifest records the project ID and uses the existing redaction path.

`DashboardService` validates that the project exists and the acting principal
is human before generating the export. A Bearer-authenticated API route calls
that service and returns the generated JSONL as a download without exposing
its workspace path. The Projects detail view adds an explicit export button.

## Interfaces

- `POST /api/projects/{project_id}/export` returns a redacted JSONL attachment.
- Unknown projects return 404; non-human callers fail closed with 403.
- A project with no events returns an empty JSONL attachment, matching the
  existing exporter rather than treating an empty history as an error.

## Failure Modes And Limits

- A subtree export could accidentally disclose sibling or descendant history.
  This slice filters exact `sessions.project_id` equality; recursive export is
  explicitly out of scope.
- Returning the generated path would disclose local filesystem structure. The
  API streams the file and returns no path.
- Secret-like event payloads could escape in the download. The existing
  redaction function remains mandatory; no unredacted mode is exposed.

## Testing

Add storage/export tests for exact-project filtering and redaction, API tests
for download, unknown project, and authentication behavior, and a Svelte test
for the explicit project export control.

## Non-Goals

- No reminder scheduler, notification delivery, retry, pause, or cancellation.
- No archive import, bulk export, attachment bundling, or descendant traversal.
