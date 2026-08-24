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
npx --prefix apps/web playwright install --with-deps chromium
npm --prefix apps/web run test:e2e:mocked
```

The mocked end-to-end suite runs against the build above and answers every API
call from a fixture, so it needs no credential and no network. CI runs it too.
The `live` suite is separate and deliberately not automated: it drives a running
`raiker-web` holding real provider credentials, and is how the FIXED-* entries in
[fixed items](../plans/FIXED_ITEMS.md) are evidenced.

```powershell
python apps/api/main.py --workspace <ws> --port 8765 --no-browser
$env:RAIKER_LIVE_ANTHROPIC_KEY = "<key>"; $env:RAIKER_LIVE_WORKSPACE = "<ws>"
npm --prefix apps/web run test:e2e:live
```

Strict non-allow blocking, role revoke governed, and capability gate per action
must remain documented and validated.

Approval resolution executes an approved local file mutation through the governed relay, along with the eleven other capabilities in `EXECUTABLE_ON_APPROVAL` (`raiker/approvals/execution.py`), and is metadata-only otherwise; unsupported capabilities are disabled and fail-closed.
