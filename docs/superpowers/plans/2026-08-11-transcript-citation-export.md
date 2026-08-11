# Transcript Citation Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export transcripts whose citation markers resolve inside the exported artifact and whose source metadata remains owner-scoped and redacted.

**Architecture:** The dashboard loads the runtime-recorded sources for each turn and passes a redacted `TranscriptSource` collection into the pure transcript builder. Renderers keep markers backed by an included source entry, remove unresolved markers, and append per-message source lists in Markdown, HTML, and PDF.

**Tech Stack:** Python dataclasses, source ledger, Markdown/HTML/PDF renderers, pytest.

## Global Constraints

- Export only sources recorded by the runtime for the authenticated owner and session.
- Never export source passages, raw tool arguments, credentials, or unredacted local paths.
- Marker cleanup is deterministic and does not alter ordinary bracketed text.

---

### Task 1: Add owner-scoped transcript source models

**Files:**
- Modify: `raiker/sessions/transcript.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `tests/test_session_transcript_export.py`

- [ ] Add failing tests with two owners and multiple turns. Assert each assistant message receives only its own turn's sources and no passage field appears in `Transcript.manifest()`.

```python
exported = service.build_session_transcript(session_id, user_id=owner_id)
assert exported.messages[1].sources[0].source_id == "s1"
assert "passage" not in exported.messages[1].sources[0].to_dict()
```

- [ ] Run `python -m pytest tests/test_session_transcript_export.py -q` and verify failure.
- [ ] Add immutable `TranscriptSource(source_id, kind, title, locator, status)` and a `sources` tuple on `TranscriptMessage`.
- [ ] Preserve `turn_id` while building transcript messages. In `DashboardService.build_session_transcript`, call `load_sources(store, session_id, principal_id, turn_id)` for assistant turns and map only redacted view fields.
- [ ] Redact titles and locators through existing redaction helpers before constructing the pure transcript model.
- [ ] Run the focused tests and verify they pass.

### Task 2: Reconcile citation markers before rendering (BUG-65)

**Files:**
- Modify: `raiker/sessions/transcript.py`
- Modify: `tests/test_session_transcript_export.py`

- [ ] Add failing tests for resolved `[s1]`, unresolved `[s2]`, repeated markers, punctuation adjacency, noncitation `[section]`, and messages with no source ledger.
- [ ] Run the focused test and verify unresolved markers remain.
- [ ] Implement a compiled `\[s[1-9][0-9]*\]` matcher. Preserve markers whose source id exists on that message and remove only unmatched citation markers, normalizing the resulting whitespace without changing ordinary brackets.
- [ ] Track `unresolved_citation_markers_removed` in the transcript manifest so exports remain auditable without pretending a source existed.
- [ ] Run the focused tests and verify they pass.

### Task 3: Render self-contained sources in all formats

**Files:**
- Modify: `raiker/sessions/transcript.py`
- Modify: `tests/test_session_transcript_export.py`

- [ ] Add failing snapshot-style assertions that Markdown, HTML, and extracted PDF text place a Sources block after the corresponding assistant message and include id, title, kind, locator, and status.
- [ ] Add hostile metadata cases containing HTML, Markdown punctuation, control characters, long paths, and secret-like text; assert escaping/redaction and bounded wrapping.
- [ ] Run the focused tests and verify failure.
- [ ] Render Markdown source entries with escaped display text, semantic HTML lists with safe escaping, and PDF source lines using the existing page-wrap logic.
- [ ] Do not create hyperlinks for deleted, changed, unsupported, or redacted locators; print their source status plainly.
- [ ] Run `python -m pytest tests/test_session_transcript_export.py -q` and verify it passes.
- [ ] Run `python -m ruff check raiker/sessions/transcript.py raiker/control/dashboard.py tests/test_session_transcript_export.py` and verify it passes.
