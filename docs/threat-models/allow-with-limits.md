# Threat model — Allow with limits and connection presets (QUI-P03, QUI-P04, QUI-P09)

An **Allow-with-limits rule** lets an ordinary action run without a fresh
prompt when the owner has already said, with limits, that it may. A
**connection preset** narrows what one connection may do. The first removes
prompts, so it is the one that needs a page: a rule is a pre-decided approval,
and a pre-decided approval is exactly what an attacker would want to mint,
widen or reuse.

## What the mechanism does

* A rule is a standing grant (`raiker/runtime/authority/grants.py`) with
  limits (`grant_limits.py`): where it applies (one conversation, one project,
  or future work), the recipients, sites, repositories or channels it may
  reach, an account, a use count (at most 100), an expiry (at most a week),
  and whether attachments and sensitive content still ask.
* **Allow for this task** on the approval card makes a rule for that
  conversation (`POST /api/approvals/{id}/limit-rule`). The rule's tool, risk
  ceiling and conversation are read from the stored approval; the request names
  only limits.
* The tool broker consults rules only for an **ordinary** approval it was
  about to park, then runs the action through the full runtime authority as an
  owner-preauthorised action, counting the use and logging
  `limit_rule_executed` with the rule's id.
* A rule for a project or for future work applies only in conversations whose
  profile is **Within limits**.
* QUI-P09 suggests a rule after three identical allows in a week. It never
  creates one.
* A connection preset (`raiker/runtime/connector_policy.py`) is Read only (the
  default for a new connection), Ask before changes, or Custom.

## Assets

| Asset | Why it matters |
|---|---|
| The owner's consent | A rule is consent given ahead of time; using it wider than given is acting without consent |
| Recipients, sites and repositories | Where a send, post or push lands is the consequence |
| Sensitive content | Credentials and secrets must not leave on a pre-decided approval |
| The audit trail | Each use must be attributable to the rule that allowed it |

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| A model mints or widens a rule | Creating a rule is human-only (`only_human_may_create_grant`, `require_human` on the route); a model has no tool that creates one | `grants.py`, `routes_limit_rules.py` |
| A client points a rule at a wider shape than the approval it saw | The tool, risk ceiling and conversation come from the stored approval; the request carries limits only, and `session_id` in the request is ignored | `routes_limit_rules.py`, `grant_limits.clean` |
| An *Always allow* by another name | Every rule expires within a week (`grant_ttl_too_long` on any grant), counts its uses, and a rule beyond one conversation must name where it may reach (`grant_limit_needs_targets`) | `grants.py`, `grant_limits.py` |
| A rule covers a critical action | Critical actions are not ordinary approvals and never reach the rule check; a rule cannot be made from a critical approval or a question, and the risk ceiling has no critical rank | `broker.py`, `routes_limit_rules.py` |
| Prompt injection names a new recipient inside a covered action | Every reached target must be inside the rule's targets; a target that cannot be read, or one of several outside, keeps the action outside the rule | `grant_limits.uncovered_reason` |
| A look-alike target (`example.com.evil.test`) | A domain matches itself or a true subdomain only; addresses match on their host | `grant_limits._within` |
| Credentials leave on a pre-decided send | Secret- and credential-like content keeps the action outside the rule unless the owner turned that limit off | `grant_limits._sensitive` |
| A rule made for one conversation is used in another | A conversation rule matches its own session only; the older router grant path skips every rule with limits | `grant_limits.py`, `router.py` |
| Careful is bypassed by a rule | Careful's turn-level `ask` forces a manual decision before any rule is consulted | `broker.py` |
| A refused action is retried past the limit | A use is spent before the attempt, like a repository delegation | `broker.py` |
| A rule silently created from repetition | Suggestions are offered, never kept; making one is the ordinary human-only create | `routes_limit_rules.py` |
| An approved write runs after the owner chose Read only | The connector invoker refuses a changing operation on a Read only connection, independently of the route | `connector_ecosystem.py` |
| An unreadable stored rule or preset | An unreadable rule covers nothing; an unknown preset reads as Read only | `grant_limits.load`, `connector_policy.get` |

## Residual risk, stated plainly

* **An address is not offered as a target.** The API redacts email addresses in
  responses, so drafts and suggestions leave them out; a rule naming a recipient
  is typed by the owner, and lists show it redacted.
* **"Sensitive" is a pattern match**, the one memory writes already use: it
  catches credential- and secret-shaped text, not every personal detail.
* **Presets apply to catalogue connections.** GitHub writes keep their own
  repository delegations (GH-50), and MCP servers their per-tool acceptance.
* **A rule spends a use even when the executor then refuses.** That is the
  conservative direction; the count may run out sooner than the owner expects.

## Evidence

* `tests/test_grant_limits.py`, `tests/test_connector_presets.py`
* `web/src/lib/limitRules.test.ts`, `LimitRuleForm.test.ts`, `SafetyCard.test.ts`,
  `ConnectionPresets.test.ts`
* [`approval-execution-relay.md`](approval-execution-relay.md),
  [`critical-approval-lifecycle.md`](critical-approval-lifecycle.md)
