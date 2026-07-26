# Local validation

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Run these checks before committing a change:

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

Build the dashboard when `apps/web` changes:

```powershell
npm --prefix apps/web ci
npm --prefix apps/web run lint
npm --prefix apps/web run check
npm --prefix apps/web run test
npm --prefix apps/web run build
```

Strict non-allow blocking, role revoke governed, and capability gate per action
must remain documented and validated.

Approval resolution is metadata-only; unsupported capabilities are disabled and fail-closed.
