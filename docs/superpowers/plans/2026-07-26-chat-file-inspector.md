# Chat File Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a view-only, session-scoped right-side/overlay inspector for PDF, Markdown, XLSX, and DOCX files already attached to or created in a chat.

**Architecture:** A session-attachment reference makes authorization explicit. The attachment route exposes only a safe preview representation; focused Svelte renderers place it in a responsive inspector without upload, edit, macro, or script execution paths.

**Tech Stack:** Python/FastAPI/SQLite/XML parsing, Svelte 5/TypeScript/Vitest, browser PDF display.

## Global Constraints

- Preview is view-only and only for session-authorized attachments/artifacts.
- Preview never executes Markdown HTML, office macros, scripts, or embedded document content.
- The wide layout uses a right-side pane; narrow layout uses a dismissible overlay.
- Unsupported, malformed, or unauthorized files have safe unavailable/404 states.

## Implementation status (2026-07-26)

This feature is specified but not implemented. There is currently no
session-authorized preview endpoint or Chat file-inspector UI. Attachments and
artifacts therefore must not be described as inspectable in the shipped chat.

---

### Task 1: Authorize and produce safe preview representations

**Files:**
- Create: `raiker/runtime/attachment_preview.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/api/routes_attachments.py`
- Modify: `raiker/runtime/attachments.py`
- Test: `tests/test_attachment_preview.py`

**Interfaces:**
- `AttachmentPreviewService.get(session_id, attachment_id, owner_id) -> AttachmentPreview | None`.
- `GET /api/sessions/{session_id}/attachments/{attachment_id}/preview` returns metadata/text preview or an inline session-authorized PDF response.

- [ ] **Step 1: Write failing scope and sanitizer tests**

```python
def test_preview_is_limited_to_the_attachment_owner_and_session(client, owner_token, other_token):
    assert client.get(PREVIEW_URL, headers=_auth(owner_token)).status_code == 200
    assert client.get(PREVIEW_URL, headers=_auth(other_token)).status_code == 404

def test_markdown_preview_escapes_raw_html_and_docx_extracts_text(store):
    assert "<script>" not in preview_markdown("# Title\n<script>x</script>").html
    assert "Quarterly report" in preview_docx(DOCX_BYTES).text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_attachment_preview.py -v`

- [ ] **Step 3: Implement references and safe parsers**

Add a `session_attachment_refs` migration and save each attachment id against the
session only after prompt ownership validation. Allow XLSX uploads through the
existing document validator. Parse DOCX/XLSX server-side with `zipfile` plus
`xml.etree.ElementTree` into bounded plain text/table rows; render Markdown from
escaped text only. Serve PDF bytes with session authorization, explicit PDF
content type, `nosniff`, and inline disposition. Return an unavailable preview
for parse errors and unsupported content.

- [ ] **Step 4: Run server verification**

Run: `pytest tests/test_attachment_preview.py tests/test_api_dashboard.py -v`

- [ ] **Step 5: Commit**

```bash
git add raiker/runtime/attachment_preview.py raiker/storage/migrations.py raiker/storage/sqlite.py raiker/api/routes_attachments.py raiker/runtime/attachments.py tests/test_attachment_preview.py
git commit -m "feat(attachments): add safe session file previews"
```

### Task 2: File inspector components and responsive Chat integration

**Files:**
- Create: `apps/web/src/lib/components/FileInspector.svelte`
- Create: `apps/web/src/lib/components/FileInspector.test.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/views/ChatView.svelte`
- Modify: `apps/web/src/lib/views/ChatView.test.ts`

**Interfaces:**
- `FileInspector` accepts `preview: AttachmentPreview | null`, `loading`, `error`, and dispatches `close`.
- `api.attachmentPreview(sessionId, attachmentId)` returns the metadata/text preview; `pdf_url` is a same-origin authorized URL.

- [ ] **Step 1: Write failing inspector tests**

```ts
await user.click(screen.getByRole("button", { name: /report\.xlsx/i }));
expect(screen.getByRole("complementary", { name: /file preview/i })).toBeInTheDocument();
expect(screen.getByText("Quarterly report")).toBeInTheDocument();
expect(screen.getByRole("button", { name: /close file preview/i })).toBeInTheDocument();
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- FileInspector ChatView`

- [ ] **Step 3: Implement the inspector**

Make attachment chips semantic buttons. Fetch only after click, render safe text
or a PDF object from the same-origin URL, and render unavailable/error states as
plain text. Use CSS grid for the wide split layout and a dialog-style overlay at
the narrow breakpoint. The inspector has no upload, mutation, or download
control.

- [ ] **Step 4: Run web verification**

Run: `npm.cmd test -- FileInspector ChatView; npm.cmd run check; npm.cmd run build`

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/components/FileInspector.svelte apps/web/src/lib/components/FileInspector.test.ts apps/web/src/lib/api.ts apps/web/src/lib/apiTypes.ts apps/web/src/lib/views/ChatView.svelte apps/web/src/lib/views/ChatView.test.ts
git commit -m "feat(chat): preview session files in an inspector"
```
