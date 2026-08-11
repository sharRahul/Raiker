# Loopback Rate Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent ordinary local navigation from exhausting the API rate limit while keeping all mutations and every public-bind request protected.

**Architecture:** The launcher passes explicit bind posture into the API factory. Rate-limit middleware exempts only GET/HEAD/OPTIONS requests when both the configured bind and actual ASGI peer are loopback. It ignores proxy headers and preserves the fixed-window limiter everywhere else.

**Tech Stack:** Python ASGI middleware, FastAPI, ipaddress, pytest.

## Global Constraints

- A loopback peer alone is insufficient when the service is public-bound.
- `X-Forwarded-For`, `Forwarded`, and `Host` never establish loopback trust.
- POST, PUT, PATCH, DELETE, and websocket paths remain limited on every bind.

---

### Task 1: Make bind posture explicit

**Files:**
- Modify: `raiker/api/app.py`
- Modify: `apps/api/main.py`
- Modify: `apps/api/launcher.py`
- Modify: `tests/test_api_rest_hardening.py`

- [ ] Add failing tests asserting `create_app(..., loopback_only=True)` records local posture and `loopback_only=False` remains conservative.
- [ ] Run `python -m pytest tests/test_api_rest_hardening.py -q` and verify the factory rejects the new argument.
- [ ] Add keyword-only `loopback_only: bool = False` to `create_app` and pass it to `RateLimitMiddleware`.
- [ ] Pass `not public` from `apps/api/main.py` and `True` from the desktop launcher. Propagate the posture to mounted instances.
- [ ] Run the focused tests and verify they pass.

### Task 2: Exempt only safe local reads (BUG-88)

**Files:**
- Modify: `raiker/api/security.py`
- Modify: `tests/test_api_rest_hardening.py`

- [ ] Add direct ASGI tests for IPv4 loopback, IPv6 loopback, public peer, missing peer, spoofed forwarded headers, safe methods, write methods, and public bind.

```python
@pytest.mark.parametrize("peer", ["127.0.0.1", "::1"])
def test_safe_reads_are_unlimited_only_on_loopback_bind(peer):
    middleware = RateLimitMiddleware(app, max_requests=1, loopback_only=True)
    assert call(middleware, method="GET", client=(peer, 5000)).status == 200
    assert call(middleware, method="GET", client=(peer, 5000)).status == 200
```

- [ ] Run the focused tests and verify the second read is currently 429.
- [ ] Add `loopback_only` to middleware construction. Resolve the ASGI client address with `ipaddress.ip_address`; catch invalid/missing values and treat them as nonloopback.
- [ ] Bypass accounting only when `loopback_only`, peer `is_loopback`, and method is GET, HEAD, or OPTIONS. Do not inspect proxy headers.
- [ ] Keep `/api` path matching, stale-client sweeping, and rate-limit reason codes unchanged.
- [ ] Run the focused tests and verify they pass.

### Task 3: Exercise navigation and mutation pressure

**Files:**
- Modify: `apps/web/e2e/critical-bugs-live.spec.ts`

- [ ] Add a live Playwright test that navigates repeatedly through all primary pages and polls ordinary read models beyond the configured limit without receiving 429 on a desktop loopback launch.
- [ ] In the same test, issue authenticated write requests past a deliberately low limit and assert the limiter still returns `reason_code="rate_limited"`.
- [ ] Launch a public-bind test instance on loopback for transport convenience but with `loopback_only=False`; assert repeated reads are limited and spoofed forwarding headers do not bypass it.
- [ ] Run `npm run test:e2e:live -- critical-bugs-live.spec.ts` from `apps/web` and verify it passes.
