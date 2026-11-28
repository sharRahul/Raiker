# Notes — linked notebook and later views

## Scope and decisions

Continue the Notes handoff from `claude/happy-elbakyan-9d89e1`. The owner chose
**Finish and verify existing Notes first** on 2026-11-28. Ordinary note edits,
memory-vault edits and Inbox lines retain the existing low-approval policy.
Do not add a mandatory approval to each edit. Memory ingestion continues to
apply its existing privacy, sensitivity and instruction scanning.

## Existing notebook delivery — 2026-11-28

- [x] Linked Markdown screen, folders, tags, properties, outline, mentions,
  local graph, search, daily notes, rename/relink and recoverable trash.
- [x] Notes screen component regressions, including conflict recovery and
  retaining an unsaved draft when navigating after a failed save.
- [x] Rename the shared control **Notes folder**; explain the default `Notes/`
  beside workspace data and that custom-folder selection also enables linked
  memory sync. Returning to default preserves existing files.
- [x] Reuse defined Quiet UI tokens, add contextual guide navigation and
  inspect desktop/phone light/dark screenshots from the real host.
- [x] Update the guide, README, FIXED_ITEMS and live-test record.
- [x] Full web suite (2,996 passed, one skipped), production build and all
  31 mocked-browser cases pass. Delivery is followed through GitHub workflows.

Evidence: [FIXED-1588](FIXED_ITEMS.md#fixed-1588--the-notes-handoff-needed-safe-editing-tests-and-a-consistent-folder-control),
[live record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-28-notes-handoff).

## Follow-up work — deliberately outside this delivery

- [ ] Full graph screen, with filtering and readable navigation for large notebooks.
- [ ] Canvas view with durable layouts and portable file representation.
- [ ] Bases-style property views, filters and sorting over note metadata.
- [ ] Agent note-writing with the existing permission/approval policy, version
  checks and audit, while note content remains untrusted reference data.

Keep this plan while those items remain open. Remove it once every item is complete.
