# GitHub Connection Specification

> **Status: Architecture Accepted / Implementation Partly Delivered — 2026-10-12.** The code-backed §18 inventory confirms sign-in, credential methods, GitHub App flow, repository delegations and the Settings journey as implemented in stated scopes; BUG-339 and real-GitHub RR-38…RR-41 evidence remain open; BUG-337 and BUG-338 closed on 2026-10-13 as FIXED-898 and FIXED-899. The managed App needs operator registration and a trusted credential service. Do not interpret implemented-against-stand-ins as externally verified.
> This document holds the protocol and contract detail behind the
> [DEC-21b amendment](../plans/RELEASE_READINESS_PRODUCT_UX_RUNTIME_REVIEW_2026-09-13.md#dec-21b-amendment-2026-10-12--hybrid-github-authentication).
> The decision record owns *what was decided and why*; this specification owns
> *how it must behave*; [ADD-27](../plans/TO_BE_ADDED.md#add-27--a-hybrid-github-connection-that-separates-sign-in-repository-access-credential-and-authority)
> owns the tasks. Nothing here is implemented unless §18 says so. A real
> GitHub App registration and live authentication evidence remain
> prerequisites for calling the managed integration verified.

## Contents

1. [Scope and principles](#1-scope-and-principles)
2. [Provider facts and design inspiration](#2-provider-facts-and-design-inspiration)
3. [Deployment modes](#3-deployment-modes)
4. [Identities and the six connection states](#4-identities-and-the-six-connection-states)
5. [Credential methods](#5-credential-methods)
6. [Sign-in flows](#6-sign-in-flows)
7. [Lifecycle](#7-lifecycle)
8. [Permission and risk matrix](#8-permission-and-risk-matrix)
9. [Repository binding](#9-repository-binding)
10. [Credential broker contracts](#10-credential-broker-contracts)
11. [Credential delivery and Git transport controls](#11-credential-delivery-and-git-transport-controls)
12. [Delegated autonomous work](#12-delegated-autonomous-work)
13. [Chat, Build, agents and the API connector](#13-chat-build-agents-and-the-api-connector)
14. [Settings → Connections → GitHub](#14-settings--connections--github)
15. [Audit](#15-audit)
16. [Webhooks](#16-webhooks)
17. [Migration and compatibility](#17-migration-and-compatibility)
18. [Current implementation gap analysis](#18-current-implementation-gap-analysis)
19. [Rejected alternatives](#19-rejected-alternatives)
20. [Acceptance tests](#20-acceptance-tests)
21. [External prerequisites and open technical questions](#21-external-prerequisites-and-open-technical-questions)

## 1. Scope and principles

The first provider is **GitHub.com** (`github.com`, `api.github.com`), as
DEC-21b accepted on 2026-10-05. GitHub Enterprise Server, `ghe.com` and other
forges are separate adapters (ADD-27 Wave 5); the GitHub.com host lists are
never widened as a shortcut.

Six principles govern every section below:

1. **Local first.** A local repository is fully usable — files, diffs,
   history, branches, commits, tests — with no GitHub connection, no App and no
   OAuth configuration.
2. **Connection is not authority.** Signing in, installing an App, selecting a
   repository and storing a credential each grant nothing by themselves.
3. **Three layers, never interchangeable.** GitHub's permissions are the outer
   limit; Raiker's capability gates, decision modes and delegations are the
   inner limit; a human approval or an explicit repository-bound delegation is
   the trigger.
4. **Detection is not consent.** A credential Raiker can see on the machine is
   offered as an option; it is never used until the owner selects it and its
   account is verified.
5. **No secret in a model-visible or agent-reachable place.** Tokens, refresh
   tokens, App private keys, client secrets, OAuth codes and PKCE verifiers
   never enter prompts, model context, transcripts, tool output, repository
   files, logs, diagnostics, events or an agent's sandbox.
6. **Fail closed, say why.** A control the broker cannot enforce makes the
   method unavailable with a named reason; it never degrades to an ungoverned
   path.

## 2. Provider facts and design inspiration

### 2.1 Verified GitHub behaviour

**How this was verified.** On 2026-10-12 `docs.github.com` could not be
reached from the review environment (DNS failure; the egress proxy refused
direct requests). The facts below were therefore checked against the
**source of those pages** — the `github/docs` repository at commit
`be38ec5d78e24172587e61b3c6ff40ace1865c71` (2026-10-09), including its shared
snippets and feature flags — for the github.com version of each page. They
are *verified from source*, not from the rendered site, and the implementing
task re-verifies them against the live pages before it ships. Items marked
**not verified** are design assumptions until then.

| # | Fact (source page in §2.3) | Consequence for Raiker |
|---|---|---|
| P1 | "In general, GitHub Apps are preferred over OAuth apps": fine-grained permissions instead of broad scopes, the installer chooses repositories, tokens are short-lived (OAuth app tokens do not expire until revoked), and the App can act with or without a user | The managed integration is a GitHub App (DEC-21b-A) |
| P2 | Three ways to authenticate: **as the App** (a JWT signed RS256 with its private key, `exp` no more than 10 minutes ahead, `iss` preferably the Client ID), **as an installation** (activity attributed to the App) and **on behalf of a user** (attributed to the user *and* the App); an App acting for a user "should always use a user access token instead of an installation access token" | Three identities, never interchangeable (§4); user work uses user tokens |
| P3 | An installation access token "will expire after 1 hour"; `repositories` / `repository_ids` (up to 500) and `permissions` narrow it, never beyond what the installation has. Enterprise-level installation tokens cannot be narrowed | Mint per operation, narrowed, in the trusted service (§5, §10); enterprise installs are Wave 5 |
| P4 | Minting an installation token needs the JWT, so the private key; a native or client-side app "should not generate installation access tokens" and "must never ship your private key" | Installation tokens are a server-side capability; no desktop build holds a key (§3) |
| P5 | User access tokens come from the **web application flow** (browser apps) or the **device flow**; by default the access token expires after **8 hours** (`expires_in` 28800) with a refresh token valid **6 months** (15897600 s); prefixes `ghu_` and `ghr_`. Expiry is on by default for new Apps and "currently an optional feature" | Expiry and refresh are first-class lifecycle states (§7) |
| P6 | The web flow takes `state` ("strongly recommended") and, on github.com, **PKCE** with `code_challenge_method` **`S256` only**; the code exchange lists `client_secret` as **Required**. A user token can be limited to one repository with `repository_id` | Browser sign-in needs a party holding the client secret (§6.2); tokens can be per-repository |
| P7 | Refresh sends `client_id`, `refresh_token` and `client_secret` — "**Required** unless the user access token was generated using the device flow"; using a refresh token invalidates it and the old access token | A device-flow sign-in can refresh with no secret (§6.4) |
| P8 | The device flow must be enabled in the App's settings and needs no client secret; `expires_in` defaults to 900 s, `interval` to 5 s; `slow_down` adds 5 s; errors include `authorization_pending`, `slow_down`, `expired_token`, `access_denied`, `incorrect_device_code`, `device_flow_disabled` | §6.3 |
| P9 | "CLI tools, simple Raspberry Pis, and desktop applications should use the device flow"; "if your app has access to a web interface, you should use web application flow instead". Best practice: do not enable the device flow except for constrained environments, because it can be used for phishing | Device flow for desktop and terminal; browser flow where a web interface exists (§6) |
| P10 | A public client "cannot secure your client secret"; GitHub's advice for one is to ship the secret and use PKCE, and it prefers PKCE over the device flow *if shipping the secret is the concern* | Recorded trade-off: Raiker declines to ship the official secret (owner rule), so desktop uses the device flow (§19) |
| P11 | A user access token has only "permissions that both the user and the app have" and reaches only resources both can access; check with `GET /user/installations` and `…/{installation_id}/repositories` | Effective permission is an intersection; the interface never claims more (§8) |
| P12 | Git over HTTPS: the token is the password and the username `x-access-token`, for installation and user tokens alike | The existing helper's convention carries over (§11) |
| P13 | Git over HTTP needs **Contents**; `.github/workflows` needs **Workflows**; PR creation needs **Pull requests: write**; merge (`PUT …/pulls/{n}/merge`) needs **Contents: write**; `PATCH /repos/{o}/{r}` needs **Administration: write**; a missing permission answers 403 with `X-Accepted-GitHub-Permissions`. **Not verified:** that Metadata: read is always granted | §8 |
| P14 | Added permissions do not take effect on an installation until its owner approves them; removed permissions take effect immediately | Raiker cannot elevate; it can only point to GitHub's approval (§8.3) |
| P15 | An App is installed on **all** or **only select** repositories; organisation owners install; a member who cannot install sends the owner a request, and the owner may change the repositories | *Organisation approval required* is its own state (§14) |
| P16 | Webhooks: `X-Hub-Signature-256` is `sha256=` + HMAC hex digest of the body under the webhook secret, compared in constant time; set a webhook secret; `github_app_authorization` (`revoked`) and `installation` (`created`, `deleted`, `suspend`, `unsuspend`, `new_permissions_accepted`) report lifecycle | §7, §16 |
| P17 | Keep the private key in a key vault, sign-only where possible; delete unused keys; encrypt tokens and store refresh tokens apart from access tokens; revoke compromised tokens (`DELETE /installation/token`, `DELETE /applications/{client_id}/token`); "never use identifiers that can change over time" for authorisation; prefer webhooks to polling. Scheduled key rotation is **not** stated (only rotation after a leak) | §9, §10; Raiker's overlap rotation is its own design choice |
| P18 | Callback URLs: up to 10; the `redirect_uri` "must be a match" for one of them; wildcard matching, still on for some older single-callback Apps, should be disabled. A varying loopback **port** is documented for OAuth apps (`127.0.0.1` or `::1`) — **not verified** for GitHub Apps | Exact redirects; loopback is an open question (§21) |
| P19 | Since 2026-04-27 newly minted installation tokens are being moved to a stateless `ghs_APPID_JWT` format; GitHub warns against assuming tokens are 40 characters | Redaction must not rely on length or the entropy fallback (GH-15) |
| P20 | GitHub Enterprise Server uses `HOSTNAME/api/v3` and has **no PKCE**; `ghe.com` data-residency tenants use their own subdomain | Wave 5 adapters, never a host-list widening |

### 2.2 Design inspiration — not vendor behaviour

Codex and Claude Code are references for the **experience**, not for their
internals, which are not documented and are not assumed here. What is taken
from their public behaviour: sign in once from a browser or a device code; pick
repositories rather than paste credentials; work on a local checkout with the
machine's existing Git setup; run cloud tasks against selected repositories
through an installed App; see which account and repository will be used before
work starts. What Raiker adds is §1's principle 2: none of those steps grants
authority by itself.

### 2.3 Sources

- [Deciding when to build a GitHub App](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/deciding-when-to-build-a-github-app)
- [About authentication with a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/about-authentication-with-a-github-app)
- [Generating a user access token for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)
- [Refreshing user access tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/refreshing-user-access-tokens)
- [Generating an installation access token for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app)
- [Generating a JSON Web Token (JWT) for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app)
- [Building a CLI with a GitHub App](https://docs.github.com/en/apps/creating-github-apps/writing-code-for-a-github-app/building-a-cli-with-a-github-app)
- [Choosing permissions for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)
- [Best practices for creating a GitHub App](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app)
- [Validating webhook deliveries](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [About the user authorization callback URL](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/about-the-user-authorization-callback-url)
- [Authenticating as a GitHub App installation](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)
- [Permissions required for GitHub Apps](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps)
- [Modifying a GitHub App registration](https://docs.github.com/en/apps/maintaining-github-apps/modifying-a-github-app-registration)
- [Installing a GitHub App from a third party](https://docs.github.com/en/apps/using-github-apps/installing-a-github-app-from-a-third-party)
- [Authorizing OAuth apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps) (device flow and loopback rules)

Read from the `github/docs` source at commit `be38ec5` on 2026-10-12 (see §2.1).

## 3. Deployment modes

| Requirement | **D-LOCAL** source install, desktop or terminal | **D-DESKTOP** official desktop release | **D-MANAGED** Raiker-managed cloud | **D-SELF** independently self-hosted |
|---|---|---|---|---|
| Local repository work (read, diff, history, branch, commit, tests) | No GitHub setup | No GitHub setup | Not applicable (cloud checkouts only) | No GitHub setup |
| Fine-grained PAT (M-PAT) | Yes | Yes | Not offered | Yes |
| gh CLI sign-in (M-GH-CLI), OS credential manager (M-OS-HELPER), SSH (M-SSH) | Yes, explicitly selected | Yes, explicitly selected | No — no user machine | Yes, explicitly selected, on the host |
| GitHub App user sign-in (M-APP-USER) | Device flow against the official App's published Client ID, or a BYO App | Device flow with the published Client ID; browser flow only through the operator's token-exchange endpoint (§6.2) | Browser flow, server-side exchange | Administrator's BYO App |
| Installation tokens (M-APP-INSTALL) | Only with a BYO App configured on the host | **No** — a desktop build holds no private key | Yes, minted by the trusted credential service | Only with a BYO App |
| What must be registered or configured | Nothing for local work; a PAT or a selected local method for remote work | The official App's **Client ID** is published in the build; **no private key, no client secret** | The official App (operator): ID, Client ID, private key and client secret in the service's secret store, callback URLs, installation mapping; verified before the feature is offered | Nothing for local methods; for App features the operator's BYO configuration (§3.1) |
| Depends on the hosted Raiker service | No | Only for the optional browser sign-in; the device flow and its refresh need nothing hosted (P7) | Yes | No |
| Webhooks | No | No | Optional, off by default | Optional, BYO, off by default |

Every unrelated Raiker feature works whether or not the official App exists.
Until GH-30 registers it, M-APP-USER is shown as *not available in this
build*, never as an error.

### 3.1 Bring your own GitHub App (D-SELF, and D-LOCAL when wanted)

Operator inputs, held as **references** (vault entry, file path with 0600
permissions, or environment variable name), never as values in a settings
file or the database in clear:

| Input | Required when | Notes |
|---|---|---|
| App ID | Installation tokens | Integer; validated by `GET /app` with a JWT |
| Client ID | Any user sign-in | Public; may be shown |
| Private key reference | Installation tokens | PEM; never leaves the trusted service; two keys may overlap during rotation |
| Client secret reference | Browser sign-in, refresh, provider-side revocation | Not needed for device-only use without refresh |
| Callback URL(s) and setup URL | Browser sign-in, post-install redirect | Must equal the registered values exactly |
| Installation ID(s) | Installation tokens | Discovered from `GET /app/installations`, confirmed by the operator |
| Webhook secret reference | Webhooks enabled | Webhooks stay off without it |
| Host contract | Always | `github.com` / `api.github.com` only until a Wave 5 adapter exists |
| Token storage | Always | The workspace vault; the trusted service's store for App credentials |

**Connection validation** checks, in order: the key signs a JWT `GET /app`
accepts; the App's permissions are no wider than §8 needs (wider is a warning
naming the excess); the Client ID matches the App; each configured installation
answers; the webhook secret exists when webhooks are on. Each failure has a
named reason and a fix. A private key is never bundled in an open-source
distribution or an installer.

## 4. Identities and the six connection states

### 4.1 Identities

| Identity | What it is | Never confused with |
|---|---|---|
| **Raiker principal** | The owner (or authorised principal) inside Raiker | A GitHub account |
| **GitHub account** | The user GitHub authenticated, keyed by its immutable numeric id; `login` is for display | The Raiker principal; another account on the same machine |
| **App installation** | The App installed on a user or organisation, with its selected repositories and granted permissions | The user's own access |
| **User access token** | Acts as the GitHub user, within P11's intersection | An installation token |
| **Installation access token** | Acts as the App on one installation | The user; Raiker's authority |
| **Raiker execution grant** | Raiker's own, shorter, operation- and repository-bound permission to lend a credential once or for a session | Any GitHub token or permission |
| **Approval / delegation** | A human's decision for an exact operation, or an explicit repository-bound delegation | A grant; a GitHub permission; a model's instruction |

### 4.2 The six states the interface keeps apart

| State | True when | Shown as |
|---|---|---|
| Connected account | A credential of some method is verified against `GET /user` and the account id is recorded | *Signed in as @login (method)* |
| Application installed | An installation of the selected App covers the account or organisation | *Raiker app installed on … (all / N selected repositories)* |
| Repository authorised | The repository id is in the installation's selection, or the PAT/method can see it | Per repository |
| Credential available | A usable, unexpired credential for that repository exists or can be minted | *Credential ready · expires …* |
| Capability enabled | The Raiker capability (`git_push_execution`, `connector_github_runtime`, future fetch/clone) is on with a decision mode | From Permissions |
| Operation approved | A grant/approval or delegation covers this exact operation and target | In the approval or task |

A single *Connected* indicator is not used anywhere.

## 5. Credential methods

| Method | Secret lives | Selected how | Account verified | Delivered to Git/API | Expires / refresh | Deployment modes |
|---|---|---|---|---|---|---|
| **M-PAT** fine-grained personal access token (existing) | Workspace vault (`github_token`, migrating to a `git_credentials` record) | Pasted in Settings | `GET /user` on save and on **Check** | Broker helper (Git), broker header (API) | GitHub-set expiry shown when the API reports it; no refresh | D-LOCAL, D-DESKTOP, D-SELF |
| **M-ENV** legacy `RAIKER_GITHUB_TOKEN` (existing) | Host environment | Implicit today; becomes an explicit method | `GET /user` on **Check** | Same as M-PAT, under the same grant (GH-13) | None | D-LOCAL, D-SELF; deprecated |
| **M-APP-USER** GitHub App user access token | Vault; the refresh token stored apart from the access token — in the trusted service for D-MANAGED, in the workspace vault otherwise (P17) | **Connect GitHub** | Token response, then `GET /user` | Broker | 8 h / 6-month refresh (P5) where enabled | All four |
| **M-APP-INSTALL** installation access token | Never stored at rest beyond its hour; minted by the trusted service | Installation + repository selection | `GET /installation/repositories` | Broker; narrowed per operation | 1 h (P3); re-minted, not refreshed | D-MANAGED; D-SELF/D-LOCAL with BYO App |
| **M-GH-CLI** existing gh sign-in | gh's own store (not copied) | **Use GitHub CLI sign-in**, choosing an account `gh auth status` lists | `GET /user` with the token read at lend time must equal the selected id | Broker reads `gh auth token --hostname github.com --user <login>` per lend | gh's | D-LOCAL, D-DESKTOP, D-SELF |
| **M-OS-HELPER** OS credential manager entry | The OS keychain (not copied) | **Use a saved Git credential**, choosing the username | As above, per lend | Broker runs the system helper's `get` for `protocol=https`, `host=github.com`, `username=<login>` in a controlled subprocess, then lends through Raiker's own helper | The entry's | D-LOCAL, D-DESKTOP, D-SELF |
| **M-SSH** governed SSH identity | Key file (path reference) or a selected agent key | **Configure SSH**, choosing a key by fingerprint | `ssh -T git@github.com` answer names the account; must equal the selected login | Constructed `GIT_SSH_COMMAND` (§11) | Key's | D-LOCAL, D-DESKTOP, D-SELF |

Methods are never silently interchangeable: a grant names its method and
account, and a lend whose method or account differs from the grant's fails
closed (`git_account_mismatch`, `git_method_mismatch`). A method the broker
cannot govern on a platform (for example a credential helper that insists on
a GUI prompt) is unavailable there with a reason.

## 6. Sign-in flows

### 6.1 Requirements common to every flow

- Fixed endpoints: `https://github.com/login/oauth/authorize`,
  `https://github.com/login/oauth/access_token`,
  `https://github.com/login/device/code`; API `https://api.github.com`. Never
  taken from configuration that a model or repository can influence.
- Exact registered redirect URIs; no wildcard or prefix matching. A loopback
  redirect is `http://127.0.0.1:<ephemeral port>/<fixed path>` and is accepted
  only when GitHub's rules for loopback redirects allow the port to vary; if
  they do not for the App in question, the desktop uses §6.3.
- `state`: 32 random bytes, stored hashed in the attempt record, compared in
  constant time, single use.
- PKCE: S256 verifier of 32 random bytes; the verifier is held encrypted in the
  attempt record and never logged.
- An **attempt record** (`github_auth_attempts`): attempt id, principal, Raiker
  session that started it, method (browser/device), state hash, encrypted
  verifier, redirect URI, created, expires (10 minutes; device: GitHub's
  `expires_in`), outcome. The callback must arrive for an attempt that is
  pending, unexpired and owned by the same principal **and session**; anything
  else is refused and recorded.
- One-time code redemption; a replayed code or state is refused.
- Cancellation (`error=access_denied`) and the owner closing the window leave
  no credential, and the attempt is closed as `cancelled` or `denied`.
- Installation (*the App is installed on these repositories*), user
  authorisation (*this user signed in*) and token creation are separate
  lifecycle states; any one can exist without the others.

### 6.2 Browser flow (authorisation code with state and PKCE)

1. Raiker creates an attempt and opens the authorise URL with `client_id`,
   `redirect_uri`, `state`, `code_challenge`, `code_challenge_method=S256`.
2. GitHub redirects to the callback with `code` and `state`.
3. The **exchange** — code + verifier + client secret → tokens — runs where the
   client secret is: the trusted credential service (D-MANAGED, D-DESKTOP via
   the operator's exchange endpoint) or the self-hosted host (BYO). A desktop
   or source build never holds the official client secret.
4. Raiker verifies the account with `GET /user`, records it (§4.1) and closes
   the attempt.

### 6.3 Device flow

GitHub's guidance for desktop applications and CLIs (P9), and the path that
needs no client secret for sign-in **or** refresh (P7, P8). It is the default
for D-DESKTOP and for terminal and headless D-LOCAL/D-SELF hosts. Where a host
has a web interface backed by a server that holds the client secret
(D-MANAGED, a BYO App on a server), the browser flow is used instead and the
device flow is not offered, because a device code can be phished into another
person's approval (P9).

1. `POST /login/device/code` with the Client ID; show the `user_code` and
   `verification_uri` (never the `device_code`).
2. Poll no faster than `interval`; on `slow_down` add five seconds for the rest
   of the attempt; stop at `expires_in`; `access_denied` and `expired_token`
   end the attempt with that outcome; at most one poller per attempt.
3. Verify the account as in §6.2 step 4.

### 6.4 Storage, refresh and account switching

- Access and refresh tokens are encrypted at rest (workspace vault, or the
  trusted service's store for D-MANAGED); a refresh token never reaches an
  agent's sandbox, a model, or an API response.
- Refresh runs where it can run without exposing a secret: in the trusted
  service or the BYO host for a browser sign-in, and locally for a
  device-flow sign-in, which GitHub refreshes without the client secret (P7).
  It runs shortly before expiry or on a 401, replaces both tokens atomically
  (the old pair stops working), and on failure marks the connection *Sign in
  again* — it never falls back to another method.
- Switching account ends every grant and lend for the old account at once and
  keeps the old account's record only for audit.

## 7. Lifecycle

| Event | Effect in Raiker | Effect at GitHub | Interface |
|---|---|---|---|
| 1. Initial authentication | Attempt → credential record for a verified account | User authorises the App / token created | *Signed in as …* |
| 2. Validation | `GET /user` (and repository visibility) on save, on **Check**, and before consequential operations | — | *Checked …* |
| 3. Storage | Encrypted; references only in records | — | Never redisplayed |
| 4. Issuance | Installation token minted per operation, narrowed; user token used as stored | Token created | — |
| 5. Renewal / refresh | §6.4 | New access + refresh token | Silent while it works |
| 6. Expiration | GitHub expiry and Raiker's grant expiry evaluated separately; the earlier wins | — | *Expired — sign in again* or *Approval expired* |
| 7. GitHub-side revocation | A 401 marks the credential revoked; pending and active grants end; tasks block | Token revoked by user/App/GitHub | *Access was revoked at GitHub* |
| 8. Raiker-side revocation | Grant revoked; lends end at the next boundary | — | *Withdrawn* |
| 9. Disconnect | All grants and lends end immediately; credential record deleted; revocation journalled (GH-16) | Token revocation attempted where supported | *Disconnected · revoked at GitHub* or *· could not confirm revocation at GitHub* |
| 10. Re-authentication | New attempt; old grants are not revived | — | — |
| 11. Account switching | §6.4 | — | Names both accounts |
| 12. App uninstallation | Installation marked removed; installation tokens unusable; user tokens lose those repositories | Installation deleted | *The Raiker app was removed from …* |
| 13. Repository permission removal | Repository marked unauthorised; grants for it end | Repository deselected / permission reduced | *Raiker can no longer see …* |

Raiker's grants (300 s *once*, 3600 s *session*) stay shorter than GitHub's
token lifetimes and are enforced independently. Nothing revoked is restored by
restoring a backup or rolling back: revocations are journalled and replayed
after a restore (GH-16), and expiry is always evaluated against the clock.

## 8. Permission and risk matrix

### 8.1 GitHub permissions

| Operation | GitHub App permission | Official App default | Raiker capability (risk) |
|---|---|---|---|
| List installations and repositories | Metadata: read (granted with any repository permission — **not verified**, P13) | Granted | none (read) |
| Read repository contents | Contents: read | Granted | future `git_fetch_execution` / connector read (high: network) |
| Clone or fetch a private repository | Contents: read + Git transport auth | Granted | future `git_fetch_execution` (high: network) |
| Create a local branch / commit | none (local) | — | `git_write_execution` (medium) |
| Push an authorised branch | Contents: write | Granted | `git_push_execution` (high) |
| Read pull requests | Pull requests: read | Granted | `connector_github_runtime` read |
| Open or update a pull request | Pull requests: write | Granted | `connector_github_runtime` write (high) |
| Read issues | Issues: read | Granted | `connector_github_runtime` read |
| Comment on an issue | Issues: write | Not in the initial default; requested when the feature ships | `connector_github_runtime` write (high) |
| Change workflow files | Workflows: write | **Excluded**; a separate, explicitly approved permission request | separate capability (critical) |
| Merge a pull request | Contents: write (+ branch rules) | Covered by Contents: write, but **not offered** by Raiker by default | separate capability (critical), never standing |
| Repository settings, branch protection | Administration | **Excluded** | none |
| Delete branches | Contents: write | Not offered by default | separate capability (high) |
| Change repository permissions, delete repositories | Administration | **Excluded** | none |

The exact permission for every REST endpoint and Git operation is confirmed
against GitHub's *permissions required for GitHub Apps* reference when GH-51
lands, and recorded beside the capability.

### 8.2 Raiker risk classes for the twelve operations

| Operation | Risk | Default decision | May a standing delegation cover it? |
|---|---|---|---|
| Read a repository (local) | low | allowed | yes |
| Fetch / clone | high (network egress) | ask | yes, for named repositories |
| Create a local branch | medium | ask | yes, named branch pattern |
| Create or amend a commit | medium | ask | yes, on a delegated branch |
| Push a branch | high | ask | yes, named repository and branch pattern, fast-forward only |
| Open or update a pull request | high | ask | yes, named repository |
| Merge a pull request | critical | ask every time | **no** |
| Modify a protected branch | critical | not offered | no |
| Change workflows | critical | not offered by default | no |
| Delete a branch | high | ask every time | no |
| Change repository permissions | — | not offered | no |
| Delete a repository | — | not offered | no |

### 8.3 Permission changes

Raiker never implies a user can raise an App's permissions from Raiker. When a
feature needs a permission the installation lacks, the interface names the
permission, why, and links to GitHub's approval page; until GitHub reports it
granted, the feature stays unavailable.

## 9. Repository binding

Every credential-backed operation carries a **binding record**: Raiker
principal; GitHub account id; installation id (if any); repository id
(authoritative), owner and name (presentation and audit); effective remote
host and URL; requested operation; required permission; execution environment;
approval or delegation reference; expiry and revocation state.

- The repository id is resolved (`GET /repos/{owner}/{repo}`) when the binding
  is made and **re-checked before each consequential operation**; a rename is
  followed by id, a transfer to another owner, a removed installation or a
  reduced permission refuses with `repository_identity_changed` or
  `repository_access_removed` and never redirects authority.
- A grant or token for one repository never authorises another; an
  installation token is minted with `repository_ids=[that id]`.

## 10. Credential broker contracts

The existing `GitCredentialBroker` becomes provider-aware rather than being
replaced. Seven separate contracts:

| Contract | Responsibility | Never |
|---|---|---|
| Discovery | Lists what is available (gh accounts, helper usernames, SSH keys by fingerprint, configured Apps) **without reading a secret** | Lends, stores or selects |
| Selection | Records the owner's choice of method and account | Happens automatically |
| Storage | Encrypts what Raiker holds; references what it does not | Re-displays a secret |
| Issuance | Mints or reads the secret for one operation (installation token, gh read, helper query) | Runs without a grant |
| Lending | Hands the secret to exactly one governed command through the broker helper or header | Puts it on a command line or in the general environment |
| Revocation | Ends grants, lends and records; journals the revocation | Is undone by a restore |
| Audit | Records non-secret metadata (§15) | Records a secret |

Invariants kept from today and extended to every method: no token in an
unrelated subprocess; no inherited environment; no token in commands, logs or
diagnostics; no lending to a host outside the credential's audience; no
automatic permission escalation; no implicit push approval; no reuse of an
expired or revoked grant; no cross-account sharing; no approval reuse after
the operation or target changes.

## 11. Credential delivery and Git transport controls

| Threat | Control |
|---|---|
| Command-line leakage | Secrets travel only in the child's private environment variable read by the inline helper (existing), or in the API request header built by the broker |
| Environment leakage / inheritance | Every git invocation — reads included (GH-24) — runs in `sandbox_environment`; `GIT_CONFIG_NOSYSTEM=1`, `HOME` set to the workspace; the secret variable exists only for the lending command |
| Credential-helper substitution | An empty `credential.helper` first, then Raiker's helper per credential host (existing); repository-level helpers are cleared by the same empty entry |
| `insteadOf` rewriting, separate push URL | The effective URL is resolved with `git remote get-url --push` (existing) and bound into the approval (GH-12); the helper answers only the credential's hosts whatever URL git ends up using |
| Submodules | No recursive clone/fetch/update; `protocol.file.allow=never`; a submodule host outside the audience receives nothing (helper check) |
| Redirects | Git: the helper is consulted per host, so a redirect to another host gets nothing. API: per-hop host check before following any redirect (closes the connector's recorded residual risk) |
| Malicious Git configuration | `core.hooksPath` to a non-existent path, `core.fsmonitor=` cleared, `uploadpack`/`receivepack` overrides refused (existing shell policy), object checks on fetch |
| Untrusted repository hooks | Never run (existing for writes, extended to reads and fetch) |
| SSH host keys | GitHub's published host keys pinned in a Raiker-owned `known_hosts`; `StrictHostKeyChecking=yes` |
| SSH agent identity selection | `IdentitiesOnly=yes`; `IdentityAgent=none` unless the owner selected an agent key, then only that fingerprint |
| Cross-repository / cross-account access | Binding record (§9); installation tokens narrowed by repository id; account checked at lend |
| Logs and output | Registered-secret redaction during the lend (existing) plus shape patterns for every GitHub token prefix (GH-15) |
| Prompt injection in issues, PRs, comments, files | Wrapped as untrusted data (existing); can never create a grant, change a decision mode or select a credential; every effect still routes through the broker and approvals |

GitHub **API** host policy (`api.github.com`) and **Git transport** host policy
(`github.com`, `ssh.github.com`) are separate entries (GH-25). If the broker
cannot enforce these controls for a method on a platform, that method is
unavailable there.

**Control plane and agent egress are different traffic.** Sign-in, the
`GET /user` account check, repository discovery, token refresh, revocation, App
validation and installation-token minting are Raiker's own requests to fixed
endpoints on `github.com` and `api.github.com`, made by one client
(`raiker/github/http.py`) that allows only those two hosts, HTTPS only, and
refuses every redirect. They are not subject to `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`,
which governs what the *agent* reaches: Git transport and the API connector's
requests on its behalf still need their host on that list.

## 12. Delegated autonomous work

A **delegation** is the owner's explicit, stored authority for repository work
without a per-step approval. Fields: delegation id; principal; repository id;
allowed operations (from §8.2's *yes* rows only); branch pattern; whether PRs
may be opened; expiry; budget; credential method and account; created by
(human only); revoked state.

Rules:

- A read delegation never writes; a branch-pattern delegation never reaches
  another branch; a PR delegation never merges.
- A scheduled task carries a delegation reference and never creates one.
- A resumed task re-validates the delegation, the credential, the
  installation, the repository id and the effective permission before its next
  consequential step (GH-52); any failure parks it as *blocked — needs owner*.
- A child agent receives at most its parent's delegation, narrowed; Git and
  GitHub write tools stay non-delegable unless the delegation names them.
- An agent never approves its own escalation; a non-human principal cannot
  create or widen a delegation (existing rule for critical approvals).
- Standing grants (`raiker/runtime/authority/grants.py`) do not cover a Git or
  GitHub write unless a delegation for that repository and operation exists.
- Every step records what the delegation allowed and what ran, so the owner can
  reconstruct both.

## 13. Chat, Build, agents and the API connector

One connection model serves:

- **Chat** — authorised read of issues and PRs as untrusted data; repository
  context; any future write goes through the same capability and approval.
- **Build** — local work without a connection; clone and fetch; branches and
  commits; governed pushes; pull requests; choosing a GitHub repository by id.
- **Autonomous agents and routines** — repository-bound delegations, refresh
  and expiry recovery, scheduled checks, approved issue-to-PR work, receipts,
  and independent verification of what was done.

**Two paths exist today and stay separately governed.** The Git push path uses
`GitCredentialBroker` (vault token, grant, host-scoped helper). The GitHub API
connector (`github_read`, `github_write`, gate `connector_github_runtime`) reads
`RAIKER_GITHUB_TOKEN` from the environment and has its own egress allowlist
check and approvals; **it does not use the broker today.** GH-56 moves the
connector onto the shared broker for credential *selection and lending only*:
the connector keeps its gate, decision mode, approval and untrusted-content
handling, and the push keeps its own capability and approval. Neither path's
approval ever authorises the other.

## 14. Settings → Connections → GitHub

**Entry.** Settings → Connections → GitHub, replacing Settings → Git credential
(which redirects there). Actions, each shown only where the deployment mode
supports it (§3):

- **Connect GitHub** (App sign-in)
- **Use GitHub CLI sign-in**
- **Use a saved Git credential** (OS credential manager)
- **Configure SSH**
- **Use a personal access token**
- **Custom GitHub App** — under *Advanced (self-hosted)*, separate from the
  ordinary flow
- **Repositories** — choose and review
- **Permissions** — what GitHub granted and what Raiker allows
- **Disconnect**

Normal onboarding never asks for a Client ID, App ID, installation token or
refresh token. Before any grant the page says which permissions are being
asked for and what they allow, in words.

**Status panel** shows the six states of §4.2 separately, plus: account,
installation type (personal/organisation, all/selected repositories), method,
effective permission level, last use, and expiry where known.

**Recovery messages.**

| Condition | Message and action |
|---|---|
| Authentication cancelled | *Sign-in was cancelled. Nothing was connected.* — Try again |
| Access denied | *GitHub did not grant access.* — Try again or use another method |
| Application not installed | *The Raiker app isn't installed on this account or organisation.* — Install on GitHub |
| Organisation approval required | *An owner of {org} must approve the Raiker app.* — Copy request link |
| Repository not selected | *{repo} isn't among the repositories the app can see.* — Choose repositories on GitHub |
| Insufficient permissions | *GitHub hasn't granted {permission}, which {operation} needs.* — Review on GitHub |
| Authentication expired | *Your GitHub sign-in expired.* — Sign in again |
| Token revoked | *Access was revoked at GitHub.* — Sign in again |
| Credentials not available | *The selected {method} credential isn't available on this machine.* — Choose another |
| Credential host mismatch | *This remote is on {host}; the credential is only for github.com.* — nothing is sent |
| Account mismatch | *The {method} credential now belongs to @{other}, not @{selected}.* — Select again |
| Network unavailable | *Couldn't reach GitHub.* — Retry; nothing was changed |
| Unsupported self-hosted configuration | *This GitHub App configuration is incomplete: {missing}.* — Open the setup guide |

Accessibility and layout follow the existing Settings contracts (390–1440
wide, light and dark, keyboard order, no inert controls).

## 15. Audit

Security-relevant events record, as metadata only: Raiker principal and
session; GitHub account id; installation id; repository id; credential method;
effective operation; approval or delegation reference; execution environment;
timestamp; result or refusal reason; provider-confirmed receipt where available
(pushed SHA read back, PR number); permission or credential change; revocation
outcome. Planned event types: `github_connected`, `github_disconnected`,
`github_auth_attempt_closed`, `git_credential_stored`, `git_credential_forgotten`,
`git_grant_created`, `git_grant_revoked`, `git_credential_lent`,
`github_installation_changed`, `github_permission_changed`,
`github_webhook_rejected`. Never recorded: access tokens, refresh tokens,
private keys, OAuth codes, PKCE verifiers, `Authorization` headers, or URLs
carrying credentials.

## 16. Webhooks

Off by default and only where a feature needs them (D-MANAGED, BYO). A delivery
is accepted only if: `X-Hub-Signature-256` verifies in constant time over the
raw body; `X-GitHub-Delivery` has not been seen (deduplicated like
`channel_inbound_events`); the installation id maps to a known installation and
principal; the event type is on the allowlist; the body is within its size
bound. The payload is untrusted data: it can wake a task that already holds a
delegation, never create authority. The existing channel signature scheme
(timestamped `X-Raiker-Signature`) is a different format and is not reused for
GitHub.

## 17. Migration and compatibility

1. The stored `github_token` stays where it is and keeps working; GH-18 adds a
   `git_credentials` record referencing it as method `pat`, without decrypting
   or re-encrypting the value and without owner action.
2. Nothing stored is deleted without the owner's action.
3. `/api/git-credential` keeps its shape; new routes are additive; any breaking
   change is versioned.
4. Grant durations (300/3600 s), revocation and push approval semantics are
   unchanged; GH-11/12/17 narrow what a grant covers and never widen it.
5. A chosen credential is never replaced by a newly detected one.
6. No permission is ever raised by migration.
7. Disconnected credentials and revoked grants are journalled so a restore
   cannot resurrect them (GH-16).
8. Migrations are additive and recoverable; a failed migration leaves the
   previous schema readable and the token usable.
9. Where the old model cannot express several accounts or providers, the new
   `git_credentials` table expresses them; the old single `github_token` row is
   not stretched to do so.

## 18. Current implementation gap analysis

Reviewed against the code on 2026-10-12 after Waves 1–4 and the Settings page
landed. "Stand-in" means proven against `tests/github_fakes.py`, not yet against
GitHub itself — that is RR-38…RR-41.

| Requirement | Status | Evidence |
|---|---|---|
| Vault-held PAT, never redisplayed | Implemented | `raiker/runtime/git_credential.py`; status fields named `credential_*` |
| Once/session grants, expiry on read, revoke, last use | Implemented | `GRANT_SECONDS`; `tests/test_git_credential_grant.py` |
| Host-scoped helper, inherited helpers cleared, token off the command line | Implemented | `credential_config`; `raiker/tools/git.py` `_credential_args`, `push_branch` |
| Push URL / `insteadOf` resolution, no URL credentials | Implemented | `proposed_push_snapshot` (`git remote get-url --push`) |
| Hooks and fsmonitor disabled on every git invocation | Implemented | `_NO_HOOKS`, `_NO_FSMONITOR` |
| Vault token usable for a proposed push | Implemented | [FIXED-882](../plans/FIXED_ITEMS.md#fixed-882--a-push-proposal-ignored-the-token-stored-in-settings-was-bug-334) |
| Session grant bound to the proposing conversation | Implemented | [FIXED-883](../plans/FIXED_ITEMS.md#fixed-883--a-this-session-git-grant-was-not-tied-to-any-session-was-bug-335) |
| Approval bound to the exact pushed commit | Implemented | [FIXED-884](../plans/FIXED_ITEMS.md#fixed-884--a-push-sent-the-branch-as-it-was-when-it-ran-not-the-commits-that-were-approved-was-bug-336); `tests/test_git_push_binding.py` |
| Legacy environment token under a grant | Implemented | an *environment* credential row, lent only under a grant — GH-13 |
| Grants bound to repository, operation, branch, credential, account | Implemented | RAIKER-2107; `covering_grant` — GH-17 |
| Account identity (`GET /user`), credential records by method | Implemented | `raiker/github/accounts.py`, `git_credentials` — GH-18 |
| Credential, grant, sign-in and delegation events | Implemented | [Event catalog](EVENT_CATALOG.md) — GH-14 |
| Revocation survives restore | Implemented | `deletion_journal` kinds for credentials, grants, delegations; `tests/test_git_credential_restore.py` — GH-16 |
| Redaction of every GitHub token prefix | Implemented | `gh[pousr]_` and `ghs_APPID_JWT` shapes; `tests/test_github_token_redaction.py` — GH-15 |
| Reads in a constructed environment | Implemented | `local_git_environment`; `tests/test_local_git_environment.py` — GH-24 |
| Separate API, Git transport and control-plane host policy | Implemented | `raiker/github/hosts.py`; §11; `tests/test_github_host_policy.py` — GH-25 |
| Clone / fetch | Implemented | `git_fetch_execution`; `tests/test_git_fetch_clone.py` — GH-23 |
| gh CLI, OS credential manager | Implemented — chosen explicitly, account re-checked at each lend | `raiker/github/local_methods.py` — GH-20, GH-21 |
| Git over SSH | Implemented — selected key, `IdentitiesOnly`, pinned host keys | GH-22 |
| Device and browser sign-in (state, PKCE), refresh with rotation, disconnect | Implemented against a stand-in | `raiker/github/auth.py`; `tests/test_github_sign_in.py` — GH-31…GH-37 |
| GitHub App service, installation tokens narrowed per operation and repository | Implemented against a stand-in | `raiker/github/app_service.py`; `tests/test_github_app_operations.py` — GH-40, GH-42 |
| BYO App configuration and validation | Implemented | `PUT /api/github/app`, Settings → GitHub → Advanced — GH-41 |
| GitHub webhook receiver | Implemented (configured App only) | `raiker/github/webhooks.py`; `tests/test_api_github.py` — GH-43 |
| Two owners never share a credential | Implemented | `tests/test_github_app_operations.py` — GH-44 |
| API connector on the shared broker | Implemented | `GithubConnectorService._borrow`; [FIXED-885](../plans/FIXED_ITEMS.md#fixed-885--an-agents-push-looked-for-a-credential-of-its-own-not-the-owners) — GH-56 |
| Repository-bound delegation; standing grants and modes excluded from pushes and GitHub writes | Implemented | [FIXED-886](../plans/FIXED_ITEMS.md#fixed-886--a-standing-grant-or-allow-mode-alone-let-an-agent-push-or-write-to-github) — GH-50 |
| …and from local branch and commit | **Implemented** 2026-10-13 | [BUG-337](../plans/FIXED_ITEMS.md#fixed-898--a-standing-git-writes-decision-covered-local-branches-and-commits-without-a-delegation-was-bug-337) |
| Risk classes for the twelve operations | Implemented | `raiker/github/delegations.py` `OPERATION_RISKS`; Settings → GitHub → Permissions — GH-51 |
| Resume revalidation before each consequential step | **Implemented** 2026-10-13 — Raiker's records every step, GitHub before a push or pull request | [BUG-338](../plans/FIXED_ITEMS.md#fixed-899--a-delegations-repository-identity-was-checked-against-the-last-discovery-not-asked-of-github-was-bug-338) — GH-52 |
| Child agents never exceed the parent's delegation | Implemented | `DelegationService.narrow`; `DELEGABLE_TOOLS` read-only — GH-53 |
| Provider receipts | Implemented — pushed ref read back; PR number and URL recorded | `read_back_ref` — GH-54 |
| Issue-to-PR routine | **Partial** — template and authority plan; no runner | [BUG-339](../plans/TO_BE_FIXED.md#bug-339--the-issue-to-pull-request-routine-has-a-template-and-no-runner) — GH-55 |
| Settings → Connections → GitHub, six states, recovery messages | Implemented | `web/src/lib/views/settings/GitHubConnection.svelte`; screenshots `docs/screenshots/2026-10-12-github-connection/` — GH-19 |
| Approvals re-governed at execution | Implemented | the relay recomputes the payload hash and re-routes; the grant or delegation is re-checked at lend time |
| Official App, managed cloud | **Blocked — external** | needs GH-30 operator registration and a trusted credential service |

## 19. Rejected alternatives

| Alternative | Why rejected |
|---|---|
| A traditional OAuth App as the managed integration | Repository-wide scopes, no installer-selected repositories, no installation identity for automation, long-lived tokens (P1) |
| Requiring every user to register an OAuth App or paste a Client ID | Makes connection a developer task; the operator registers once (DEC-21b-A, -O) |
| Shipping the official client secret or private key in desktop builds | The private key must never ship (P4). For the client secret GitHub says a public client cannot protect it and suggests shipping it with PKCE (P10); the owner's rule is that no distributable package carries it, and the device flow — GitHub's recommendation for desktop apps (P9) — gives sign-in and refresh without it. Cost: the device flow's phishing exposure, mitigated by showing the account before anything is granted and by connection granting nothing |
| Device flow everywhere | Phishable; worse UX where a browser flow works (§6.3) |
| Inheriting the machine's credential helper, SSH agent or environment | Uses whichever account signed in last, unscoped and unrevocable by Raiker — the reason FIXED-578 cleared inherited helpers |
| Treating installation as consent to write | Collapses GitHub's permission and Raiker's authority into one layer |
| Broadening `CREDENTIAL_HOSTS` or accepting an arbitrary OAuth issuer | Sends one forge's token to another; Wave 5 adapters instead |
| One *Connected* indicator | Hides which of the six facts is missing (§4.2) |
| Replacing the broker with a new GitHub service | Loses tested guarantees; the broker is extended |

## 20. Acceptance tests

Automated (unit/integration with fake GitHub endpoints) unless marked *live*
(a consented test account and repository) or *manual*. Mocks never stand in
for live evidence of GitHub authentication.

**Authentication.** First connection succeeds (*live*); cancel; deny; invalid
state refused; PKCE verifier mismatch refused; redirect mismatch refused;
attempt expiry; device-flow expiry, `slow_down` and polling floor; account
switch isolates old credentials; expired credential triggers *Sign in again*.

**Repository access.** Selected repository succeeds (*live*); unselected
refused; removed access detected; transfer does not carry authority;
organisation approval pending handled; two accounts cannot reach each other's
credentials; a read-only installation cannot write.

**Governance.** Connecting does not authorise a push; read permission never
writes; a denied push contacts no remote; an approved operation cannot change
before execution (FIXED-884); session grants expire and stay in their session
(FIXED-883); revocation ends pending and active grants; a scheduled agent cannot
elevate; a child never exceeds its parent; Stop prevents later unapproved
effects.

**Security.** Canary secrets absent from logs, transcripts, model context,
events and screenshots; no token to an unrelated host; redirects and
`insteadOf` cannot bypass host policy; malicious submodules get no credential;
helpers cannot silently select another account; SSH bound to the selected
identity and pinned host; spoofed or replayed webhooks refused; GitHub content
cannot change policy; expired or revoked credentials unusable after restart and
after restore.

**Compatibility.** Existing stored PATs keep working (FIXED-882);
push approval semantics preserved; old databases migrate; failed migration
recoverable; rollback cannot restore revoked authority; local development works
without OAuth; self-hosted works without the managed service.

**End-to-end scenarios** are RR-37…RR-41 in
[release acceptance](../plans/RELEASE_ACCEPTANCE_TEST_SCENARIOS.md#h-github-connection-and-repository-authority--dec-21b).

## 21. External prerequisites and open technical questions

**External prerequisites (not blockers for local work).**

- The official Raiker GitHub App registration (GH-30) — App ID, Client ID,
  private key and client secret held by the operator's secret store.
- A trusted credential service deployment for D-MANAGED and for D-DESKTOP
  browser sign-in and refresh.
- Consented GitHub test accounts (two users, one organisation) and test
  repositories for live evidence.

**Status 2026-10-12.** Waves 1–4 are implemented and tested against a stand-in
GitHub. Still external: GH-30 (no official Client ID is published, so *Connect
GitHub* appears only with a configured custom App or `RAIKER_GITHUB_APP_CLIENT_ID`),
the trusted credential service, and live evidence with consented accounts
(RR-38…RR-41). Wave 5 is deferred by the decision.

**Open technical questions (to settle in the named task, not owner decisions).**

- Whether GitHub accepts a varying loopback port for a GitHub App's
  registered callback (documented for OAuth apps only, P18). It matters only
  if a desktop browser sign-in is added later (GH-32); the default desktop path
  is the device flow, which needs no callback.
- Whether `DELETE /applications/{client_id}/token` can revoke a device-flow
  user token without the client secret. Implemented conservatively: without the
  secret a disconnect reports *could not confirm* rather than claiming a
  revocation (GH-37).
- The exact shape of the stateless `ghs_APPID_JWT` installation token (P19),
  so that GH-15's pattern matches it whole, including any `.` separators.
- Whether a token from `gh auth token` for a selected account can be read
  without gh refreshing or switching its active account on every supported gh
  version (GH-20).
- Which OS credential helpers can be queried non-interactively for a named
  username without a GUI prompt (GH-21); those that cannot are unavailable.
