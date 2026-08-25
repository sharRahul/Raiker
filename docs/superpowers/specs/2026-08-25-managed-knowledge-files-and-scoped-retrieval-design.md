# Managed Knowledge Files and Scoped Retrieval

Date: 2026-08-25

## Outcome

Raiker will provide one managed, owner-scoped knowledge system for uploaded files, approved memories, project files, and conversation history. Chat can retrieve relevant context from the owner's complete Raiker workspace. Build must have one selected project and can retrieve only account memory, that project's files, and conversations assigned to that project.

The same change completes the desktop workspace refresh by removing project and theme controls from the application top bar, adding file and folder management to Memory and Projects, and standardising related icon controls without materially changing the existing colour palette.

## Current State

Raiker already has the foundations this design extends:

- Approved memory is stored as Markdown under `.raiker/memory/` and projected into the encrypted database, lexical search, vectors, and the memory graph.
- Uploaded chat documents are validated, stored in the encrypted database, and locally extracted for bounded turn context.
- Projects currently own roots under `projects/<slug>/`, have project instructions and attachment references, and can scope sessions.
- The context gatherer already performs owner-wide hybrid memory recall and relevant conversation recall.
- The Knowledge Map can browse managed project roots, generated files, approved memory, and explicitly granted external folders.
- Chat and Build currently inherit an account-level active project, while Build also exposes its own conversation project picker.

The implementation must consolidate these paths rather than create another memory or indexing subsystem.

## Storage Architecture

### Managed roots

Original files are stored in owner-controlled managed roots:

- Account memory files: `.raiker/memory-files/`
- Project files: `.raiker/projects/<project-slug>/`
- Approved atomic memories: `.raiker/memory/`
- Conversation transcripts: encrypted database records and their search projections

Every uploaded file type is accepted for Memory and Projects. Raiker preserves the original bytes, filename, relative directory structure, media-type observation, size, content hash, timestamps, owner, and scope.

Acceptance does not imply extraction. Text-capable formats are extracted and indexed. Unsupported, encrypted, malformed, or binary formats remain valid stored files with metadata-only searchability. Raiker never executes a file because it was uploaded and never treats extracted file content as instructions.

### Metadata and projections

The encrypted database remains the authoritative catalogue for managed files. A file record links the original to:

- its owner and logical scope;
- its managed relative path and content hash;
- extraction and index status;
- extracted text chunks, when available;
- lexical, vector, and graph projections;
- provenance used by retrieval results;
- lifecycle state and the latest indexing error.

This is not a second memory system. Parsed file chunks enter the same governed retrieval pipeline as approved memories, with a distinct source kind and immutable provenance back to the original file.

### Directory imports

Projects and Memory both support adding individual files and complete folders. Folder imports preserve relative hierarchy. The server rejects absolute paths, traversal, symlink escapes, reserved internal paths, and paths that exceed configured limits.

Imports are staged and committed atomically per file. A failure in one file does not roll back successfully stored siblings. Name conflicts are reported before replacement; existing content is not overwritten silently. Content hashes allow exact duplicates to be recognised without falsely merging two different logical locations.

### Existing project migration

Existing project roots under `projects/<slug>/` move to `.raiker/projects/<slug>/` through an idempotent migration. The migration:

1. resolves both source and destination beneath the workspace;
2. preserves project identifiers, relative paths, and file bytes;
3. records and reports destination conflicts;
4. updates `root_subpath` only after the project has a valid destination;
5. can resume safely after interruption;
6. leaves a conflicted project on its previous valid root until the conflict is resolved.

Project deletion continues to operate only on the exact contained managed root belonging to the selected project.

## Retrieval Boundaries

### Chat

Chat has no project selector. For the authenticated owner, hybrid retrieval can rank:

- approved account and project memories;
- indexed files from `.raiker/memory-files/`;
- indexed files from every owned project;
- relevant prior Chat and Build conversations;
- project metadata needed to explain provenance.

Retrieval is relevance-ranked and bounded; it does not inject every source into a turn. Results identify their source kind, project when applicable, original file or conversation, and the signals that produced the match.

### Build

Build requires exactly one selected project before work can start. Its retrieval boundary is:

- approved account-wide memory;
- indexed files from `.raiker/memory-files/`;
- approved memory scoped to the selected project;
- files from the selected project's managed root;
- conversations assigned to the selected project.

Build must not retrieve files, project memories, or chats belonging to another project. Unassigned chats are excluded from Build retrieval. Changing the selected project changes the filesystem, context, and retrieval boundary together and is not permitted during an active turn.

The backend, not the visibility of a UI selector, enforces these rules. Every retrieval query is owner-scoped first and project-scoped where Build requires it.

### Conversation storage

Chat and Build transcripts remain in their dedicated encrypted database tables. Existing conversation full-text search is retained and becomes one leg of the shared retrieval coordinator. Conversation content is not duplicated into loose files. Search chats remains the explicit discovery surface for browsing all conversations.

## Ingestion and Indexing Flow

1. The browser sends files plus a target scope: account memory or a specific owned project.
2. The API authenticates the owner, validates the scope, normalises each relative path, and enforces containment and upload limits.
3. The storage service writes the original atomically to the managed root and records catalogue metadata.
4. The extraction service detects whether a safe local extractor exists. It extracts bounded text when possible and otherwise marks the item metadata-only.
5. The index coordinator chunks extracted text and updates lexical, vector, and graph projections with file provenance.
6. The UI polls or refreshes item status until each file is ready, metadata-only, or failed.

Initial extraction support reuses the existing TXT, Markdown, CSV, PDF, DOCX, and XLSX readers. Additional formats can be added behind the extractor interface without changing storage or retrieval contracts. Legacy `.doc` and `.xls` files are stored immediately but remain metadata-only unless a safe local extractor is available.

Indexing is retryable and idempotent by file revision. Replacing a file retires stale chunks and projections before publishing the new revision. Moving or renaming a file updates catalogue provenance without changing its bytes. Deleting a file retires every projection linked to that file.

## Desktop UI

### Application shell

The top bar retains the navigation toggle, page title and description, notifications, host/runtime controls, and emergency stop. The global project selector and theme toggle are removed.

Theme choice remains in Settings → Personalisation with Light, Dark, and System options. System is the default and is represented by the absence of a stored override.

### Build

Build owns its project selector in the work-surface header, where the execution boundary is visible throughout the session. With no project selected, the composer explains that a project is required and does not start a turn. The selector uses owned projects and folders but always resolves to one concrete project identifier.

### Projects

The selected project detail receives a grouped import control containing “Add files” and “Add folder”. Its file browser shows the managed project path, preserved hierarchy, size or type metadata, index state, and per-file errors. Import progress and retry actions remain local to the project detail.

Project selection on this page is for viewing and management. It no longer establishes an application-wide context. “Start in Build” explicitly opens Build with that project selected. Starting Chat from a project does not narrow Chat's retrieval boundary.

### Memory

Memory receives the same grouped “Add files” and “Add folder” actions. A document-library section is distinct from approved atomic memory records while sharing filters, provenance presentation, and indexing status language. This keeps an uploaded workbook distinguishable from an approved remembered statement.

### Control consistency

Related non-destructive icon actions may be grouped into segmented toolbars. Destructive actions, primary actions, and unrelated toggles remain separate. Shared control contracts are:

- compact controls: 32 px;
- normal controls: 40 px;
- prominent or touch-critical controls: 44 px;
- one shared icon-button component and icon size scale;
- consistent radii, focus rings, hover states, disabled states, and dropdown geometry.

The current palette remains. Contrast improvements come from semantic borders, surface elevation, text hierarchy, and state styling rather than new brand colours. The existing collapsible sidebar and 12-column desktop layout remain the shell model.

## Failure Handling and Safety

- Invalid ownership or scope fails closed without disclosing another owner's files.
- Traversal, symlink escape, and protected internal path attempts are rejected before writing.
- Partial folder imports return an itemised result: stored, duplicate, metadata-only, failed, or conflicted.
- Extraction failures never destroy the stored original.
- Index failures can be retried and never leave stale projections marked current.
- File content is labelled untrusted data in model-facing context.
- Binary and active content is never executed automatically.
- Retrieval remains bounded by result count and character budget.
- Project migration conflicts are visible and do not overwrite either side.

## Test Strategy

Backend tests will cover:

- owner isolation and exact Chat/Build retrieval boundaries;
- Build's required-project enforcement;
- all-file storage for both Memory and Projects;
- safe extraction and metadata-only fallbacks;
- folder hierarchy preservation and path containment;
- duplicate, conflict, replacement, rename, and deletion lifecycle behavior;
- idempotent project-root migration and interrupted migration recovery;
- projection creation, deduplication, retirement, and provenance;
- conversation retrieval filtering by selected Build project.

Frontend tests will cover:

- absence of project and theme controls from the top bar;
- System as the default theme in Settings;
- Build's selected-project requirement and persistent boundary indicator;
- Memory and Project file/folder imports, progress, errors, and retry;
- accessible names, focus order, keyboard operation, dropdown behavior, and grouped controls;
- standard control dimensions and states.

Verification will include the full relevant Python and web test suites, production web build, desktop-width browser checks, 4K bounded-layout checks, and refreshed `docs/screenshots/pages/**` desktop captures. A sub-agent will review the completed implementation before the final commit and push to `origin/main`.

## Implementation Sequence

1. Introduce managed-file catalogue, storage boundaries, and project-root migration.
2. Add safe ingestion, extraction adapters, and projection lifecycle.
3. Add scoped file and conversation retrieval to the existing hybrid coordinator.
4. Enforce Chat and Build retrieval contracts server-side.
5. Remove global project and theme controls; make Build own project selection.
6. Add Memory and Projects file/folder management.
7. Standardise icon grouping and control geometry across affected and individually reviewed desktop views.
8. Run migrations, tests, accessibility and browser verification, refresh screenshots, obtain sub-agent review, commit, and push `main`.

## Non-goals

- Executing arbitrary uploaded files.
- Claiming content search for formats Raiker cannot safely parse.
- Synchronising managed roots with external folders after import.
- Introducing a second memory database or a parallel retrieval engine.
- Allowing Build to retrieve from unselected projects or unassigned conversations.
- Materially changing Raiker's existing colour palette or navigation information architecture.
