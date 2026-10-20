# Troubleshooting

Raiker refuses with a **named reason code** rather than failing vaguely. Each
one has a specific fix. Since the Models sign-in dialog now prints the fix
alongside the code, this table is the complete reference.

## Connecting a model

Three codes that used to block a first-time setup no longer occur when you
connect a provider through the app — configuring it is your authorization, the
endpoint you configured is authorised with it, and the vault key provisions
itself. They remain below because they can still appear for a provider you have
**not** configured, or one you explicitly revoked.

| Reason code | Meaning | Fix |
|---|---|---|
| `provider_requires_explicit_policy_approval` | You have configured no provider, or you explicitly turned this one off | Connect the provider in **Models**. If you previously turned **Hosted models** off in Permissions, turn it back on — an explicit revocation outranks a saved connection. |
| `hosted_provider_requires_explicit_policy` | Same, for hosted providers | As above |
| `private_network_provider_requires_explicit_policy` | Same, for a home-lab endpoint | As above, via **Home-lab models** |
| `model_connection_required` | The provider is off this machine and you have not connected it. A key in the environment is not a connection | Connect it in **Models** — paste the key, or tick **Use the key from `<VARIABLE>`** |
| `model_connection_origin_mismatch` | The request would go to an address other than the one the saved connection was made for — usually an `endpoint_env` override that changed after you connected | Reconnect the provider with the address you want |
| `model_connection_origin_unbound` | The saved connection names no address and the profile has none of its own | Reconnect and enter the endpoint |
| `endpoint_userinfo_rejected` / `endpoint_ambiguous_host` | The endpoint embeds a user name or password, or writes its host in a form that could mean more than one address (`127.1`, `0x7f.0.0.1`) | Use a plain host name or dotted IPv4 address, and put the key in the key field |
| `image_connection_origin_mismatch` | Design: this provider's connection is saved for a custom endpoint, so its key is not sent to the provider's image service | Connect the provider without a custom endpoint to generate images |
| `redirect_refused:<status>` | The provider answered with a redirect; Raiker does not follow one with your key | Check the endpoint is the provider's real API address |
| `environment_credential_unavailable` | You asked to use the key from the environment, and Raiker's environment does not have it | Paste the key, or set the variable and restart Raiker |
| `connector_vault_key_invalid` | The stored key is not a valid Fernet key | Settings → Security & sign-in → Generate key |
| `connector_vault_key_unset` | Only on a **read**: credentials exist but the key is gone, so they cannot be decrypted | Restore the key, or clear and re-enter the affected credentials. Writes provision a key automatically; reads deliberately do not, because minting a new key would hide a real problem. |
| `hosted_api_key_missing` | Hosted provider needs a key | Paste it into the sign-in dialog |
| `provider_api_key_missing:<VAR>` | Key absent from dialog and environment | Paste it, or set `<VAR>` before starting |
| `model_name_not_configured` | No model pinned on the profile | **Choose model…** on the provider card |
| `missing_endpoint` / `missing_endpoint_env:<VAR>` | No endpoint configured | Use **Advanced: custom endpoint**, or set `<VAR>` |
| `openrouter_requires_https` | OpenRouter needs HTTPS | Remove or fix the custom endpoint |
| `unknown_provider:<name>` | Unrecognised provider in a profile | Fix the profile in `raiker/config/model-profiles.json` |
| `test_provider_not_available` | Raiker ships no mock provider | Pick a real backend |
| `configured_model_store_unavailable` | Raiker could not read *which model you chose*. This is a failure of the workspace database, not of the model, the key, or the provider — your choice is still saved | Check the workspace directory is readable and not out of disk, then try again. Raiker refuses the turn rather than quietly running on a different model, and it deliberately does not tell you to re-pick a model you have already picked. |
| `model_not_checked` | This exact profile, model and endpoint has never been checked | Open **Models**, choose the model, and press **Check again**. (An *expired* check needs nothing from you: Raiker re-takes it as it admits the turn.) |
| `local_runtime_unreachable` / `local_runtime_missing` | The selected Ollama, LM Studio, or llama.cpp service is stopped or absent | Start/install the named runtime, pull or load the exact model, then check again. |
| `local_model_missing` / `provider_model_missing` | The provider is reachable but its catalogue does not contain the exact selection | Pull, load, or choose a listed model. |
| `provider_execution_refused` | A hosted catalogue succeeded, but a one-token execution preflight was refused for a reason Raiker could not classify further | Review the provider credential and model entitlement, then check again. |
| `provider_workspace_required` | The key is identity-linked, so it acts inside one workspace and the provider will not accept a request that does not name which | Add the workspace ID under **Advanced** in the connection dialog — it is beside the key in the provider's console. The key is fine; only the request was incomplete. You can add it to a saved connection without re-pasting the key. |
| `provider_workspace_invalid` | A workspace **was** named and the provider did not recognise it | Check the workspace ID on the connection against the one in the provider's console. This is not the same as the code above: nothing is missing, one value is wrong. |
| `workspace_id_invalid_shape` | The workspace ID you typed could not safely become an HTTP header — a stray newline, a non-printable character, or over 128 characters | Retype it. Raiker refuses it before storing anything rather than sending it. |
| `provider_quota_exhausted` | The provider accepted the credential and then refused to run the model because the account has no credit or quota left. Anthropic returns this as HTTP 400 on a valid key; OpenAI as `insufficient_quota`; most OpenAI-compatible routers as HTTP 402 | Add credit or raise the quota on that provider's account, then check again. Rotating the key will not help — it is not the credential that is wrong. |
| `reasoning_budget_exceeds_output_limit` | Thinking is on, this model takes the *budgeted* spelling of extended thinking, and the turn's maximum output is too small to hold the model's minimum thinking budget **and** an answer. `max_tokens` counts both | Raise `max_tokens` on the profile in `raiker/config/model-profiles.json` (the shipped `anthropic-hosted` profile uses 16000), or set **Thinking** back to default. Nothing is wrong with the key or the model. |
| `model_unavailable: provider_error_unclassified` | A legacy or mid-turn provider failure that could not be classified | Return to **Models** and run the readiness check. BUG-69 prevents this from being a fresh user's first action. |
| `model_unavailable: provider_stream_failed:<Type>` | The provider connection ended in an exception nothing else classified; the exception class is in the code. Raiker already re-attempted the same model once | Retry. If it repeats, the class names the layer — a `RemoteProtocolError` or `ConnectError` is the network between you and the provider; the server log carries the same line. |

**How a model destination is decided.** Connecting a provider authorises that
connection's own address — scheme, host and port — and nothing else. There is
no blanket opening and no environment list to maintain: a host that belongs to
no connection you saved is not reachable for model calls. The old
`RAIKER_MODEL_EGRESS_ALLOWLIST` is ignored; Raiker notes once in its log if it is
still set.

## Capabilities and runtime

| Symptom | Cause | Fix |
|---|---|---|
| A surface says "enable it in Capabilities" but the gate **is** on | The gate is at `enabled_policy_gated`, not `enabled_runtime` | Turn it on again from **Permissions** and pick the runtime level. If it still will not go, the agent runtime itself is disabled — Settings → Runtime configuration → Enable |
| `activation_blocked: runtime_mode_not_active` | The agent runtime is disabled. It no longer names one of five modes — there is one runtime | Settings → Runtime configuration → **Enable agent runtime** |
| **Turn on** is missing entirely | Deferred capability — no governed executor exists | Nothing to do. The deferred set is named in [Capabilities with no enable path](permissions-and-runtime-modes.md#capabilities-with-no-enable-path) |
| `Confirm change` stays greyed out | Reason, confirmation token, or threat-model tick missing | The confirmation token is **any phrase you type** — it records intent, it is not a credential |
| `disabled_by_capability_gate` from an API call | Gate off for your account | Permissions → find the capability → Turn on |

## Chat and turns

| Symptom | Cause |
|---|---|
| "No model is selected yet, so the runtime will refuse the turn" | Choose a profile in Models, or the Chat model selector |
| Raiker forgets what you said one message ago | **Fixed.** Prior completed turns of the session are replayed to the model, bounded by the model's context window. A turn with no reply is skipped, and other chats are never mixed in. |
| Reply shows `# heading` and `\|table\|` as raw text | **Fixed** (FIXED-06). Replies render as Markdown, with each code block labelled by language and carrying a keyboard-reachable **Copy code**. Your own prompts are deliberately shown exactly as typed. |
| Part of a reply reads `[REDACTED_TOKEN]` or `[REDACTED_EMAIL]` | Working as intended — the response layer masks the matched span of anything credential-shaped. Prose that merely *mentions* a secret is left alone (**fixed**, FIXED-07). |
| "Context capacity is not configured for this model" | That profile has no documented context window. Honest, not an error. Set one exactly under **Models → Details → Context window override**. |
| A model you run yourself answers but never uses tools | **Models → Details → Check this server** says whether the server refuses tools, returns them as text, or the model simply does not call them, and which server setting fixes it. |
| An approved file write produced no file | **Fixed** (FIXED-08). An approved `write_file`/`edit_file`/`apply_patch` is carried out once, re-governed at execution time and checkpointed first. If it still records only, one of `approval_execution_relay` or the target's own capability is off in Permissions, and the approval detail says so before you decide. |
| An approved **network** or **process** action produced nothing | By design — those two keep metadata-only resolution (`executes_action: false`). The parked turn still continues, with an honest "approved, but not executed" result. |
| `provider_connection_failed` | The provider was unreachable — check network, endpoint, and the fallback sequence |
| "X could not be reached. Check this device's network access, and any proxy or firewall between it and the provider." | A **hosted** provider Raiker could not classify a refusal from, because nothing answered. Raiker does not guess at a cause here; what it can tell you is which remedies exist. A corporate proxy or an egress rule that does not allow the provider's host is the usual one. |
| "X could not be reached. Check that it is running and reachable from this device." | The same, for a **local** runtime — Ollama, LM Studio, llama.cpp. Here starting the service is a thing you can actually do, which is why the two sentences differ. |
| "The connection to Raiker ended before this turn finished." | The browser lost the stream — Raiker itself may still be running. It says this rather than blaming the local runtime, which it has no way to know is unreachable; if the turn had already shown you something, that is kept and the sentence says so. Check Observability, or send it again. |
| A turn ends with a sentence naming a `reason_code` in brackets | Raiker refused the turn before the model saw it, and the code is the refusal. The sentence is the runtime's own explanation; the code is what to quote when asking for help. It replaced an HTTP status number, which could not tell a rejected key from a scope decision. |
| Raiker asks "Send this again?" and lists what the first attempt did | **Retry re-runs the turn.** The first attempt wrote a file, ran a command or sent a message, and retrying does those again. Raiker cannot tell whether repeating them is safe, so it names them and leaves the decision to you. A turn that only read is never queried. |

## Server and session

| Symptom | Fix |
|---|---|
| Reload returns you to the lock screen | Expected. The bearer token is in memory only, never `localStorage`. |
| Lock screen: *The workspace key (.raiker/app.key) is missing, but the database it unlocks is still here* (`store_key_missing`) | The key file was moved or lost. Raiker will not make a new one — a new key cannot open this data. Put the original `app.key` back from your backup and restart. Nothing in the workspace was changed. |
| Lock screen: *this workspace key does not open it, or part of the file is damaged* (`store_unreadable`) | The key in `.raiker/` is not the one the database was made with, or the database file is damaged. Raiker writes nothing over it. Restore the matching `app.key` and restart, or use **Restore from a backup** on the lock screen (in a browser on the same machine): the damaged database is moved to `.raiker/quarantine/` and the verified backup put in its place. |
| Lock screen: *last opened by a newer Raiker* (`store_schema_newer`) | A newer version of Raiker last shaped this database, and this one will not open it as a downgrade. Start the newer Raiker again, or restore a backup this version can open from the lock screen — the newer database is kept in `.raiker/quarantine/`. |
| Permissions: *This permission was changed somewhere else since this page loaded* | Another tab or device changed it after this page opened; nothing was changed here. The page now shows the current setting — choose again if you still want to change it. |
| Tasks: *An earlier attempt of this task was already saved* | The draft was saved on an earlier press whose answer was lost, then edited. Check the queue before saving it again. |
| Account → Backups: *Damaged — …* or *Unreadable* | *Damaged* means the file changed after it was made (a checksum or integrity failure): remove it and back up again. *Unreadable* means it was made with a different `app.key` than this workspace's; it opens only with that key. Neither is offered for restore. |
| Settings: *Not saved: a setting you changed here was also changed somewhere else* | Another tab or page saved the same setting after this page opened. Your edits are still on the page; **Show the newer settings** loads what was saved, and you can make your change again on top of it. |
| A request answered 415 `request_body_encoding_unsupported` | The client compressed its request body. Raiker reads only uncompressed bodies; send it without `Content-Encoding`. |
| `Refusing to bind to non-loopback host … without --allow-public` | Add `--allow-public` **and** set `RAIKER_OWNER_TOKEN` |
| Dashboard is blank or stale | `npm --prefix web run build`, then restart `raiker-web` |
| Backend change has no effect | Restart `raiker-web` — Python is not hot-reloaded |
| Too many device sessions listed | Settings → Security & sign-in → revoke individually, or change your password to sign out all other devices |

## Environment variables

| Variable | Purpose |
|---|---|
| `RAIKER_MODEL_EGRESS_ALLOWLIST` | **Retired** and ignored. Model providers are authorised by the connections you save in **Models**. Remove it. |
| `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` | Hosts service connectors may be reached on |
| `RAIKER_CONNECTOR_VAULT_KEY` | Overrides the workspace vault key file |
| `RAIKER_OWNER_TOKEN` | Required with `--allow-public` |
| `RAIKER_WEB_UI_DIR` | Alternative dashboard build directory |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `HF_TOKEN`, `OLLAMA_API_KEY` | Provider keys, if you prefer the environment over the vault |

## Desktop app

| What you see | Meaning | Fix |
|---|---|---|
| Raiker Setup: *This computer doesn't meet Raiker's requirements yet* | A requirement listed under it is not met (memory, free storage, operating system, architecture) | Do what the listed item says, then **Try again**. Nothing was created, so there is nothing to clean up. |
| Raiker Setup: *Raiker took too long to start* / *stopped while it was starting* / *Part of Raiker is missing* | The bundled host did not start or verify | **Try again**. If it repeats, **Open logs** (`logs/setup.log`) and reinstall: your data is outside the app and is kept. |
| Raiker Setup opens by itself on a later start | Raiker did not start, so it is being checked again | Follow the screen. To run the checks on purpose, start Raiker with `--repair`. |
| Windows installer: a ✖ on *Checking this computer*, and **Next** is greyed out | Memory, or free space for the program or your data, is below the minimum | Free space (or choose another folder with **Back**), or use a computer with at least 4 GB of memory. Nothing has been installed. |
| `apt`/`dnf`: *Raiker was not installed: this computer does not meet its requirements* | Less than 4 GB of memory | Use a computer with at least 4 GB of memory. |
| *Raiker's host stopped before it was ready* / *did not become ready* (in the window) | The bundled host could not start | Open Raiker again. If it repeats, reinstall: your data is outside the app and is kept. |
| *Windows protected your PC* | A test build that is not code-signed | Use a signed release. Only for a build you trust: **More info → Run anyway**. |
| macOS: *"Raiker" can't be opened* | An unsigned test build downloaded from the internet | Use a signed, notarised release. |
| Windows installer: *Raiker needs Windows 10 version 1809 or newer* / *a 64-bit edition* | Unsupported Windows | Update Windows, or use a supported computer. |
| This device: **Needs attention** on Memory, Storage, Operating system or Architecture | A minimum requirement is not met | Follow the fix shown on the row. Raiker may not work correctly until it is met. |
| This device: *Credential protection — private file* | No OS key store is available (common on headless Linux, or when the keyring is locked) | Provider keys are still encrypted. To use the Secret Service, install and unlock GNOME Keyring or KWallet, then restart Raiker. |
| `vault_keystore_unavailable`, or Check: *The vault key cannot be read* | Your provider keys' protection key is held by the OS key store, which did not answer (locked keyring, different user) | Unlock your keyring (or sign in as the user who set Raiker up) and restart Raiker. Raiker never replaces the key, because a new one could not read your saved keys; if the keyring item is truly lost, reset the vault in Settings and enter your provider keys again. |
| Check: **Governed command runner** — `native_sandbox_artifact_missing` / `…_digest_mismatch` | The command runner inside the installation is missing or altered | Reinstall Raiker. Chat works meanwhile; Build cannot run commands. |
| Check: **Data format** — *written by a different Raiker version* | This data was migrated by a newer Raiker | Install that newer version again, or restore the backup taken before the update. |
| Updates: `desktop_update_manual` | Raiker was installed from a `.deb`, `.rpm` or `.msi`, which your system package manager owns | Download the new release's package and install it over the old one. |
| Updates: `release_signature_invalid`, `artifact_digest_mismatch`, `release_version_mismatch` | A downloaded update did not match its signed manifest | Nothing was installed. Check the channel URL and key; try again later. |
| Updates: `channel_url_invalid` | The update channel is not HTTPS, or redirects | Pin a channel host that serves files directly over HTTPS. |

## Where to look next

- **Observability → Overview** — runtime state, readiness, memory integrity, and
  the reason and remediation for any readiness check that failed.
- **Observability → Audit log** — every governed step, filterable.
- **[To be fixed](../plans/TO_BE_FIXED.md)** — known defects with reproductions.
- **[Live manual test plan](../plans/TESTING.md)** — what
  was verified working, with screenshots.
