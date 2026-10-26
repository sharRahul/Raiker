# Remote access

How the owner reaches Raiker from another device, and what protects it.
Decided by the owner on 2026-10-26 (BUG-347, BUG-358); implemented and verified
in [FIXED-1266](../plans/FIXED_ITEMS.md#fixed-1266--a-proxy-that-sent-no-forwarding-header-was-still-read-as-local-bug-347-review)
and [FIXED-1267](../plans/FIXED_ITEMS.md#fixed-1267--remote-access-was-gated-by-a-token-nothing-read-bug-358).

## Decisions

1. **Raiker's own listener is on this computer, always** (`127.0.0.1`). It is
   never configured, never public, and never a reverse proxy's destination.
2. **Other devices reach Raiker through one remote listener**, off by default,
   chosen in **Settings → Security → Remote access**:

   | Mode | Listener | HTTPS |
   |---|---|---|
   | This device only (default) | none | — |
   | Private network | a private or VPN address of this computer (`10/8`, `172.16/12`, `192.168/16`, `100.64/10` as Tailscale uses, `fc00::/7`) | Raiker serves it with the owner's certificate and key |
   | Reverse proxy | `127.0.0.1:<port>`, or a Unix socket (`0660`, not on Windows) | the proxy terminates it and says so with `X-Forwarded-Proto: https`, which Raiker believes on this listener only |

3. **The listener a connection arrived on decides whether it is local**, not
   anything the request says (`raiker/api/proxy_guard.py`). A forwarding
   header on the local listener is refused (`proxied_request_refused`); every
   request on the remote listener is remote, whatever its headers.
4. **Two-step sign-in is the key; there is no shared secret.**
   `RAIKER_OWNER_TOKEN` is removed (BUG-358). It was a start-up requirement
   whose value nothing ever read: it promised a second credential that did not
   exist, made remote access depend on a value an owner had to create, store and
   copy, and would not have suited the mobile apps that will reach Raiker later.
   The owner's password and an MFA code are what admit another device.

## Local and remote authentication

| | This computer | Another device |
|---|---|---|
| Sign in | password, then a code when MFA is on | password **and** a code, always; refused while any account has no MFA (`remote_access_suspended`) |
| Session | cookie (`HttpOnly`, `SameSite=Strict`) and a bearer token for the CLI | cookie only (`HttpOnly`, `Secure`, `SameSite=Strict`); no bearer token is returned |
| Lifetime | 7 days idle, 30 days at most | 12 hours idle (sliding), 7 days at most |
| Sensitive changes | password or a code | password **and** a code |
| Recovery, instances, host Quit/Restart, tray exchange, remote-access changes | allowed (with the checks each already has) | refused (`loopback_only`), whatever the session |
| Turning remote access off | allowed | allowed, takes effect at once |

Enforced in the server, on every authenticated request
(`AuthMiddleware._require_remote_assurance` in `raiker/api/auth.py`), so no
client and no route can skip it. A remote request is accepted only on a session
that:

- was established from another device (`origin = remote`),
- was verified with a code (`assurance = mfa`),
- against the MFA enrolment in force now (`mfa_epoch` equals the account's).

So a session made on this computer — password-only or not — opens nothing
remotely, and a token copied off the machine is useless. Turning MFA off or
resetting it moves the account's enrolment counter, which retires every session
verified against the old one, and signs out every other device.

## Fresh MFA

Turning MFA off, resetting it, applying a remote-access setting and rolling one
back need an elevated session granted, within five minutes, **on a code** from
the current enrolment (`require_fresh_mfa`). A password-only elevation is
refused with `fresh_mfa_required`. A reset is staged: the current authenticator
keeps working — and remote access with it — until the new one's first code is
confirmed. A recovery code counts as a code, which is how an owner who lost the
authenticator resets it.

## Suspension

Remote access is **suspended** whenever an account has no MFA:

- at start, the remote listener is not opened (`suspended_mfa`);
- while running, every remote session is refused and remote sign-in answers
  `remote_access_suspended`;
- turning MFA off records a `suspended` event and notifies the owner.

Turning MFA on again lifts it; a listener that was not opened at start needs a
restart.

## Configuration lifecycle

`raiker/app/remote_access.py` keeps one row: the configuration the owner chose
(*desired*), the one before it (*previous*, the rollback target) and what the
last start did. Nothing is applied silently:

1. **Check** (`POST /api/remote-access/check`): ports and conflicts with the
   local listener, a port or socket another program holds, an address that is
   public, unspecified, loopback or not this computer's, TLS files that are
   missing, unreadable, mismatched, expired or readable by other users, a Unix
   socket on Windows, a socket path too long, MFA readiness.
2. **Review and apply** (`POST /api/remote-access/apply`): this computer only,
   fresh MFA, and an explicit confirmation of who will be able to reach the
   sign-in page. A setting that fails a check is refused, not saved.
3. **Restart.** A host registered as a service restarts itself (Restart
   returns exit status 75, which systemd and launchd restart on); otherwise
   the owner quits and opens Raiker again. Until then Settings says
   *Waiting for a restart* and shows nothing as open.
4. **Start** (`prepare`, shared by `raiker-app` and `raiker-web` through
   `raiker/app/host_start.py`): opens exactly the saved setting. A setting that
   cannot open falls back to the previous one and says so (`fell_back`), or
   starts this device only (`failed`); an unreadable setting starts this device
   only. **Invalid never means exposed.**
5. **Roll back** (`POST /api/remote-access/rollback`): fresh MFA, this
   computer only, for the next start.
6. **Turn off** (`POST /api/remote-access/disable`): any signed-in session.
   The remote listener refuses everything from that moment
   (`remote_access_disabled`) and closes at the next restart.

`raiker-web` start options (`--proxy-port`, `--proxy-socket`,
`--private-host` with `--tls-cert`/`--tls-key`) open a listener for that start
only; Settings shows them and does not change them. `--allow-public` and a
non-loopback `--host` are retired; `RAIKER_TRUSTED_PROXY` stops the host from
starting.

## What the owner sees

- **Settings → Security → Remote access**: remote access *On / Off — this
  device only / Suspended / Waiting for a restart / Not working*; connection
  method and address; two-step sign-in *Enrolled / Required / Verification
  needed*; HTTPS *Verified / Not verified yet*; problems in words; Set up or
  Change (a guided dialog), Turn off, Details (last start, recent events, Go
  back). The values are what the running host reports.
- **Settings → Security → Signed-in devices**: each session's browser as the
  browser reports it (shown as such, never treated as identity), *This
  computer* or *Another device*, *Signed in with a code* or *Password only*,
  last activity; Sign out one, or all other devices.
- **Host menu**: *Reachable from* reads the host's own status.
- **Diagnostics → Overview**: requests a proxy sent to the wrong listener,
  remote access on or suspended, HTTPS never seen through the proxy, remote
  sign-in and code failures in the last 24 hours, a start that failed or fell
  back. No credential, code, secret or session token appears there.

Remote access decides **who can reach Raiker**. What Raiker may do is still
Permissions and approvals, unchanged: a remote session grants no capability and
skips no approval.

## Platforms

| | Linux | macOS | Windows |
|---|---|---|---|
| Private network (TLS) | yes | yes | yes |
| Reverse proxy, port | yes | yes | yes |
| Reverse proxy, Unix socket | yes | yes (path ≤ 100 characters) | no — refused with *use a port* |
| Restart from Settings | when registered with `systemd --user` | when registered with `launchd` | quit and open Raiker again |
| Port claim | `SO_REUSEADDR` (rebinding `TIME_WAIT` only) | same | `SO_EXCLUSIVEADDRUSE`, so a port in use is never shared |

## Security regression scenarios

Each is a test; the live cases are in [WEB_APP_LIVE_TEST.md](WEB_APP_LIVE_TEST.md).

| Scenario | Evidence |
|---|---|
| Local access works with remote access off, without MFA | `test_local_access_works_without_mfa` |
| Remote access cannot be enabled without MFA | `test_check_names_missing_mfa_first`, `test_no_mfa_means_no_listener`, RT-SEC-04 |
| Password alone never opens a remote session | `test_password_alone_yields_only_a_ticket_remotely`, RT-SEC-08 |
| Password and a code sign in, cookie-only, protected | `test_password_and_code_sign_in_with_a_protected_cookie`, RT-SEC-08 |
| Wrong or missing codes are refused, logged, and lock out | `test_wrong_codes_are_refused_logged_and_lock_out` |
| Sessions from this computer never work remotely | `test_local_sessions_do_not_work_remotely` |
| MFA off suspends; a reset retires old verifications | `test_turning_mfa_off_suspends_remote_access`, `test_an_mfa_reset_is_staged_and_retires_old_verifications`, RT-SEC-10 |
| Proxy-listener requests are remote without headers; spoofed headers grant nothing | `test_the_proxy_listener_is_remote_without_any_forwarding_header_but_https`, `test_a_real_server_tells_its_listeners_apart`, RT-SEC-03 |
| Local-only endpoints refuse another device | `test_local_only_operations_refuse_another_device`, RT-SEC-08 |
| Remote requests are rate limited; sign-in keeps the strict window, a signed-in session gets a wider one | `test_proxied_reads_are_rate_limited_in_their_own_bucket`, `test_a_signed_in_client_has_a_wider_window_of_its_own` |
| Wrong proxy routing is diagnosed | `test_diagnostics_names_the_listener_and_the_refusals`, RT-SEC-01/02 |
| The setting survives a restart | `test_the_setting_survives_a_restart_and_opens_as_saved`, RT-SEC-07 |
| Invalid configuration fails closed | `test_an_unreadable_setting_starts_this_device_only`, `test_a_setting_that_will_not_open_with_nothing_to_fall_back_to_is_closed`, RT-SEC-12 |
| Failed changes roll back | `test_a_setting_that_will_not_open_falls_back_to_the_previous_one`, `test_manual_rollback_restores_the_previous_setting`, RT-SEC-12 |
| Revocation works across devices | `test_signing_out_other_devices`, `test_one_session_is_revoked_by_id`, RT-SEC-09 |
| HTTPS and session protections | `test_remote_requests_without_https_are_refused`, `test_a_real_tls_listener_serves_https_and_is_remote`, `test_sign_in_answers_are_never_cached` |
| UI status matches the running listener | `test_status_reports_the_running_listener_not_the_wanted_one`, RT-SEC-06/07 |
| Windows, macOS, Linux | CI job *Remote access* (Windows, macOS) and the full suite (Linux) |
| Disable takes effect at once, from another device | `test_disable_from_another_device_takes_effect_at_once`, RT-SEC-11 |
