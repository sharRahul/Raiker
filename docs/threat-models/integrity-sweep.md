# Threat Model — Background Integrity Sweep (F2 / ZT-4)

`scheduled_routines` may run the metadata-only `routine_type: integrity_sweep`.
It creates a per-owner baseline on its first successful run, then checks the
event hash chain, API-session validity, capability-gate/decision-mode drift,
and model/connector/channel egress-allowlist drift.

Green runs create no notification. A deviation creates one owner-scoped
`integrity_deviation` dashboard notification with only a count; no event body,
session token, credential, or allowlist value is exposed. The routine is
on-demand through the existing scheduled-routines executor—there is no daemon
or new authority path.

The baseline is owner settings data. It never enables a gate, changes an
allowlist, revokes a session, or repairs an event chain; those remain explicit,
governed owner actions.
