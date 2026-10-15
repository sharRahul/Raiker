# Quiet UI Design

## Goal

Make every Raiker screen calmer and faster to scan by using Manrope for interface text, JetBrains Mono only for machine-readable values, and concise operational copy.

## Typography

- Remove Source Serif 4 declarations, the serif token, and bundled Source Serif assets.
- Use Manrope for body copy, headings, page titles, and display headings.
- Retain JetBrains Mono only for code, preformatted output, keyboard keys, paths, identifiers, diffs, and other machine values.
- Update the stylesheet contract test so the allowed font policy is explicit.

## Copy policy

- Apply the cleanup to every Svelte view and shared component.
- Keep a page title, primary action, relevant status, validation message, error, approval explanation, and accessibility label.
- Remove static page ledes, duplicated helper paragraphs, decorative captions, and instructions whose associated control is self-explanatory.
- Replace any necessary instructional sentence with the shortest unambiguous wording rather than hiding safety, consent, or irreversible-action context.

## Verification and workflow repair

- Fix the mypy TypedDict inheritance error in `raiker/api/wire/sessions.py` without changing the wire shape.
- Run the Python, web, native, static-analysis, and build checks represented by the non-release workflows.
- Commit only files changed by this work, push `main`, then verify the resulting GitHub Actions runs.

## Boundaries

- Do not alter dynamic model responses, audit evidence, approval payloads, error details, or screen-reader-only labels merely to reduce visible copy.
- Do not modify or commit pre-existing unrelated worktree changes.
