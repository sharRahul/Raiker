# Chat search and project deletion

## Scope

Make **Search Chat** a real search over saved conversations, and allow an owner to permanently delete a project, its scoped chats, and its project folder.

## Chat search

- Keep Search Chat separate from the Sessions audit view.
- Use the existing magnifying-glass icon in navigation.
- Add an authenticated search endpoint that searches a user's session titles and persisted turn prompt/summary text. It returns one result per matching session, ordered by most recently updated, with the session title and a safe matching-text preview.
- The page queries that endpoint after a non-empty search term and lists matching conversation titles. It does not expose session IDs.
- Selecting a result routes to New Chat with the selected session ID carried internally in the route. ChatView rehydrates that conversation from the existing session/turn API and sends later prompts with that session ID, continuing the original runtime conversation.
- No fuzzy index, background job, or new dependency: SQLite matching is sufficient for the existing local runtime.

## Project deletion

- Add an authenticated `DELETE /api/projects/{project_id}` endpoint gated by the same human gate-manager authority as creation and selection.
- The service validates the project, clears it as active when necessary, then performs one SQLite transaction that deletes the project's sessions and dependent chat records/checkpoints before deleting the project row.
- After database deletion, recursively delete only the verified workspace-contained project root. Reject a missing or escaped root; do not accept a client-supplied path.
- The Projects card exposes Delete. A native confirmation dialog states: “This will permanently delete all project chats and files in this project folder. To save chats, move them to your chat list or another project before deleting.”
- Refresh the projects list and shared topbar state after success; show the server error without pretending deletion happened on failure.

## Error handling and tests

- Search returns no results for a blank query and never searches across another user's sessions.
- Search tests prove title/content matches, session-title-only results, and continuation routing.
- Deletion tests prove all scoped chats/checkpoints/project metadata and the project root are gone, unscoped records remain, the active selection clears, and unknown/unauthorized projects fail closed.
- The folder delete is constrained to the project root derived and checked server-side. Database deletion and filesystem deletion report failures honestly; no success response is fabricated.
