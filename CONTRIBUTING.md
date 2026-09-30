# Contributing to Raiker

Keep changes focused, update the affected canonical documentation, and run the
validation commands in [docs/architecture/LOCAL_VALIDATION_GATE.md](docs/architecture/LOCAL_VALIDATION_GATE.md).

Use Python 3.11+, install `.[dev]`, and keep generated caches, build outputs,
virtual environments, and credentials out of commits. Add or update tests for
behaviour changes.

Comments in executable files state the invariant, the non-obvious reason for it
and what fails without it — plus any external protocol fact needed to stay
compatible. How the code arrived there ("before BUG-X this did Y") belongs in
the commit and its `docs/plans/FIXED_ITEMS.md` entry; cite the ID instead of
retelling it. Never shorten a comment at a security boundary to save lines.

Contributions are licensed under the repository's Apache-2.0 license. Report
security vulnerabilities privately as described in [SECURITY.md](SECURITY.md).
