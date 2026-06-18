# Local Validation Gate while GitHub Actions are paused

## Reason

GitHub Actions are temporarily paused because the Actions run limit/quota is exhausted.

During this period:

- GitHub CI is not the source of truth.
- No PR or branch should be considered validated unless local validation evidence is recorded.
- Developers must run the full validation set locally before merge or main push.
- The validation evidence must be copied into the PR body or `docs/IMPLEMENTATION_STATUS.md`.

This is a temporary infrastructure pause only. It is not a waiver of validation requirements, phase status rules, or runtime safety gates.

## Required local validation commands

Run the full set from a clean virtual environment before merge or any main push:

```bash
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
raiker --help
raiker --prompt "Hello Raiker"
```

For Phase 3 rollout branches, also run manual or scripted smoke coverage for:

```text
/help
/status
/capabilities
/semantic-memory
/execution-profiles
/workspace
/clients
/plugins
/plugin-plan
/doctor
```

## Required evidence format

Record this evidence in the PR body or `docs/IMPLEMENTATION_STATUS.md`:

1. Branch and commit tested
2. OS
3. Python version
4. Virtual environment
5. Commands run
6. Test result totals
7. CLI smoke results
8. Confirmation that the following remain disabled:
   - plugin execution
   - graph/codemap runtime indexing
   - semantic/vector memory writes
   - external channels
   - subagents
   - multi-agent teams
   - remote execution
   - container execution
9. Files changed
10. Commit SHA
11. Remaining risks
12. Statement that GitHub Actions are paused due quota and must be re-enabled later

## Re-enable requirement

Restore `pull_request` and `push` triggers for the CI and Phase Status Validation workflows when Actions quota is available again. Full CI must be re-enabled before future release tagging.
