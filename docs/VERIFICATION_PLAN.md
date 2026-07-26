# Verification plan

CI runs one Python 3.11 job on pull requests and pushes to `main`. It runs the
full pytest suite, Ruff, mypy, and source compilation. Separate workflows run
licensing and phase-status validation; the web workflow runs only for web changes.

## Required local checks

```powershell
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
python -m compileall -q raiker apps tests
python scripts/validate_phase_status.py
python scripts/validate_repo_truthfulness.py
python scripts/validate_documentation_truthfulness.py
python scripts/validate_runtime_enablement_readiness.py
python scripts/validate_local_single_user_runtime.py
```

For dashboard changes, also run the web lint, check, test, and build commands
listed in [LOCAL_VALIDATION_GATE.md](LOCAL_VALIDATION_GATE.md).
