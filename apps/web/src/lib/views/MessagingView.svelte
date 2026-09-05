<script lang="ts">
  /**
   * Messaging — where Raiker meets you somewhere other than this browser.
   *
   * This was a tab inside Extensions, beside connectors, MCP servers, skills,
   * hooks and plugins. Those are all things the agent *uses*; a channel is a
   * place a person reaches the agent from, which is a different kind of thing
   * and now has its own destination.
   *
   * The governing idea has not changed and is the whole reason this page reads
   * the way it does: **a channel message is untrusted content with a named
   * sender who is not you.** Every transport lands on the same path — a
   * pairing, an allowlisted sender, a per-sender budget, a redacted preview, an
   * audit event, and a routing decision the owner stored out of band. Telegram
   * gets no shortcut for being a name you recognise.
   */
  import { onMount } from "svelte";
  import GuideLink from "../components/GuideLink.svelte";
  import { api, ApiError } from "../api";
  import type { ChannelProfile, ChannelsView } from "../apiTypes";

  let channels = $state<ChannelsView | null>(null);
  let channelsError = $state<string | null>(null);
  let channelBusy = $state<string | null>(null);
  let channelNotice = $state<string | null>(null);
  let pairingFor = $state<string | null>(null);
  let pairSenders = $state("");
  let testFor = $state<string | null>(null);
  let testUrl = $state("");
  let routingFor = $state<string | null>(null);
  let routeMode = $state<"record_only" | "new_turn" | "side_question" | "interrupt">("record_only");
  let routeTarget = $state("");
  let routeOwner = $state("");
  let routeRelay = $state(false);

  const CHANNEL_REASONS: Record<string, string> = {
    disabled_by_capability_gate:
      "The external channel capability is turned off. Turn it on in Permissions to deliver anything.",
    channel_already_paired: "That connector is already paired.",
    sender_allowlist_required:
      "This channel accepts inbound messages, so it needs at least one allowlisted sender before it can be paired.",
    channel_not_paired_or_disabled: "Pair the connector and switch it on first.",
    unknown_channel_pairing: "That pairing is no longer there.",
    not_authorized_human: "Only you can change a channel pairing.",
    channel_owner_not_allowlisted: "Choose an owner sender from this channel's allowlist.",
    channel_owner_sender_required: "This route needs an explicit owner sender.",
    channel_target_session_required: "Side questions and interrupts need a target conversation.",
    channel_target_session_unknown: "That conversation is unavailable to this account.",
    telegram_bot_token_missing:
      "Telegram delivery needs RAIKER_TELEGRAM_BOT_TOKEN in the host environment. Raiker takes the variable name, never the token itself.",
    telegram_chat_id_missing:
      "Bind an owner sender for this pairing, or give a chat id, before delivering to Telegram.",
  };

  function channelReason(error: unknown): string {
    if (!(error instanceof ApiError)) return "That request failed.";
    const code = error.reasonCode ?? "";
    if (CHANNEL_REASONS[code]) return CHANNEL_REASONS[code];
    if (code.startsWith("egress_denied"))
      return "That host is not on the channel egress allowlist, so delivery was refused before it left this machine.";
    if (code.startsWith("http_error"))
      return `The destination answered with an error (${code.split(":")[1] ?? "unknown"}).`;
    if (code.startsWith("fetch_failed"))
      return "The destination could not be reached.";
    if (code.startsWith("unknown_connector")) return "That connector is not in the registry.";
    return code || "That request failed.";
  }

  async function loadChannels() {
    try {
      channels = await api.channels();
      channelsError = null;
    } catch (error) {
      channels = null;
      channelsError =
        error instanceof ApiError ? error.message : "Channel profiles are unavailable.";
    }
  }

  async function runChannelAction(key: string, action: () => Promise<unknown>, done: string) {
    if (channelBusy) return;
    channelBusy = key;
    channelsError = null;
    channelNotice = null;
    try {
      await action();
      channelNotice = done;
      await loadChannels();
    } catch (error) {
      channelsError = channelReason(error);
    } finally {
      channelBusy = null;
    }
  }

  function pair(profile: ChannelProfile) {
    const senders = pairSenders
      .split(/[\n,]/)
      .map((entry) => entry.trim())
      .filter(Boolean);
    void runChannelAction(
      `pair:${profile.connector_id}`,
      () => api.pairChannel(profile.connector_id, profile.display_name, senders),
      // Said at the moment it happens, because "paired" is the step most likely
      // to be read as "working".
      `Paired ${profile.display_name}. It is switched off until you turn it on.`,
    ).then(() => {
      pairingFor = null;
      pairSenders = "";
    });
  }

  function sendTest(profile: ChannelProfile) {
    const url = testUrl.trim();
    if (!url) return;
    void runChannelAction(
      `test:${profile.connector_id}`,
      () => api.deliverChannelTest(profile.connector_id, url, "Raiker test delivery."),
      "Delivered. The destination accepted it.",
    );
  }

  function openRouting(profile: ChannelProfile) {
    routingFor = routingFor === profile.connector_id ? null : profile.connector_id;
    routeMode = profile.routing_mode ?? "record_only";
    routeTarget = profile.target_session_id ?? "";
    routeOwner = profile.owner_sender_id ?? "";
    routeRelay = profile.approval_relay_enabled ?? false;
  }

  function routeLabel(mode: ChannelProfile["routing_mode"]): string {
    if (mode === "new_turn") return "New turn";
    if (mode === "side_question") return "Side question";
    if (mode === "interrupt") return "Interrupt";
    return "Record only";
  }

  function saveRouting(profile: ChannelProfile) {
    void runChannelAction(
      `routing:${profile.connector_id}`,
      () => api.setChannelRouting(profile.pairing_id ?? "", {
        routing_mode: routeMode,
        target_session_id: routeTarget.trim() || null,
        owner_sender_id: routeOwner.trim() || null,
        approval_relay_enabled: routeRelay,
      }),
      routeMode === "record_only"
        ? `${profile.display_name} records inbound messages without starting work.`
        : `${profile.display_name} now routes ${routeMode.replace("_", " ")}.`,
    ).then(() => (routingFor = null));
  }

  onMount(loadChannels);
</script>

{#if channelsError}
  <div class="notice notice-danger" role="alert">{channelsError}</div>
{/if}
{#if channelNotice}
  <div class="notice notice-ok" role="status">{channelNotice}</div>
{/if}

<section class="card" data-testid="channel-posture">
  <h2>Channels</h2>
  <p>
    A channel message is <strong>untrusted content with a named sender who is not you</strong>.
    It cannot raise a turn's authority.
  </p>
  <p class="note">
    Linked, enabled, trusted, and reachable are separate.
    <GuideLink route="messaging" label="How a channel is governed" />
  </p>
  {#if channels !== null}
    <ul class="event-list">
      <li class:event-dead={!channels.outbound.runtime_enabled}>
        <strong>Outbound</strong>
        <span class="hook-tag" class:hook-tag-dead={!channels.outbound.runtime_enabled}>
          {channels.outbound.runtime_enabled ? "Capability on" : "Capability off"}
        </span>
        <span class="note">
          {channels.outbound.runtime_enabled
            ? "Governed and audited."
            : "Turn on external channel runtime in Permissions."}
        </span>
      </li>
      <li class:event-dead={!channels.outbound.egress_configured}>
        <strong>Egress</strong>
        <span class="hook-tag" class:hook-tag-dead={!channels.outbound.egress_configured}>
          {channels.outbound.egress_configured
            ? `${channels.outbound.egress_host_count} host${channels.outbound.egress_host_count === 1 ? "" : "s"}`
            : "None allowlisted"}
        </span>
        <span class="note">
          Set <code>RAIKER_CHANNEL_EGRESS_ALLOWLIST</code>; empty denies all hosts.
        </span>
      </li>
      <li class:event-dead={!channels.outbound.signing_configured}>
        <strong>Signing</strong>
        <span class="hook-tag" class:hook-tag-dead={!channels.outbound.signing_configured}>
          {channels.outbound.signing_configured ? "Signed" : "Unsigned"}
        </span>
        <span class="note">
          Set <code>RAIKER_CHANNEL_OUTBOUND_SECRET</code> for HMAC-signed delivery.
        </span>
      </li>
      <li class:event-dead={!channels.inbound.secret_configured}>
        <strong>Inbound</strong>
        <span class="hook-tag" class:hook-tag-dead={!channels.inbound.secret_configured}>
          {channels.inbound.secret_configured ? "Secret set" : "Refusing everything"}
        </span>
        <span class="note">
          Set <code>RAIKER_CHANNEL_INBOUND_SECRET</code>; unset refuses every message.
        </span>
      </li>
      <li>
        <strong>Rate limit</strong>
        <span class="hook-tag">
          {channels.inbound.rate_limit_per_minute ?? 60}/min
        </span>
        <span class="note">
          Per sender and channel; refusals are recorded. Override with
          <code>RAIKER_CHANNEL_INBOUND_RATE</code>.
        </span>
      </li>
    </ul>
  {/if}
</section>

<section class="card" data-testid="channel-profiles">
  <h2>Connectors</h2>
  {#if channels === null}
    <p class="note">{channelsError ?? "Reading connector profiles…"}</p>
  {:else if channels.error}
    <p class="note">The connector registry could not be read, so nothing is offered here.</p>
  {:else}
    <ul class="hook-list">
      {#each channels.profiles as profile (profile.connector_id)}
        <li>
          <div class="channel-head">
            <strong>{profile.display_label ?? profile.display_name}</strong>
            <span class="hook-tag" class:hook-tag-dead={!profile.linked}>
              {profile.linked ? (profile.enabled ? "On" : "Linked, off") : "Not linked"}
            </span>
            {#if profile.requires_sender_allowlist && profile.linked}
              <span class="hook-tag" class:hook-tag-dead={profile.sender_count === 0}>
                {profile.sender_count} sender{profile.sender_count === 1 ? "" : "s"}
              </span>
            {/if}
            {#if profile.linked}
              <span class="hook-tag">{routeLabel(profile.routing_mode)}</span>
              {#if profile.approval_relay_enabled}<span class="hook-tag">Approval relay</span>{/if}
            {/if}
          </div>
          <span class="note">
            {profile.transport} · {profile.auth_method}{profile.requires_network
              ? " · needs network"
              : " · local only"}
          </span>

          <!-- What this transport needs from the environment, declared on the
               connector profile rather than left to the guide. The idea is
               Hermes Agent's `plugin.yaml` requires_env/optional_env, which
               drives its setup wizard; here it answers the question an owner
               actually has in front of a channel that will not send — *which
               variable, and is it set*. Whether, never what: Raiker takes the
               name of a variable and never its value, and that holds on this
               surface too. -->
          {#if profile.env_requirements?.length}
            <ul class="env">
              {#each profile.env_requirements as need (need.name)}
                <li class:env-missing={need.required && !need.present}>
                  <code>{need.name}</code>
                  <span class="hook-tag" class:hook-tag-dead={!need.present}>
                    {need.present ? "Set" : need.required ? "Missing" : "Not set"}
                  </span>
                  <span class="note">
                    {need.description}
                    {#if need.url}<a href={need.url} target="_blank" rel="noopener noreferrer">Where to get it</a>{/if}
                  </span>
                </li>
              {/each}
            </ul>
          {/if}

          {#if profile.linked}
            <div class="channel-actions">
              <button
                type="button"
                class="btn btn-sm"
                disabled={channelBusy !== null}
                onclick={() =>
                  void runChannelAction(
                    `enable:${profile.pairing_id}`,
                    () => api.setChannelEnabled(profile.pairing_id ?? "", !profile.enabled),
                    profile.enabled
                      ? `${profile.display_name} is off.`
                      : `${profile.display_name} is on.`,
                  )}
              >{profile.enabled ? "Turn off" : "Turn on"}</button>
              <button
                type="button"
                class="btn btn-sm"
                disabled={channelBusy !== null}
                onclick={() => {
                  testFor = testFor === profile.connector_id ? null : profile.connector_id;
                  testUrl = "";
                }}
              >Send a test delivery</button>
              <button
                type="button"
                class="btn btn-sm"
                disabled={channelBusy !== null}
                onclick={() => openRouting(profile)}
                aria-expanded={routingFor === profile.connector_id}
              >Routing</button>
              <button
                type="button"
                class="btn btn-sm btn-danger"
                disabled={channelBusy !== null}
                onclick={() =>
                  void runChannelAction(
                    `unpair:${profile.pairing_id}`,
                    () => api.unpairChannel(profile.pairing_id ?? ""),
                    `${profile.display_name} is unpaired. Nothing can reach it now.`,
                  )}
              >Unpair</button>
            </div>
            {#if testFor === profile.connector_id}
              <form
                class="channel-form"
                onsubmit={(event) => {
                  event.preventDefault();
                  sendTest(profile);
                }}
              >
                <label class="field-label" for={`test-${profile.connector_id}`}>
                  Destination URL
                </label>
                <input
                  id={`test-${profile.connector_id}`}
                  class="input"
                  bind:value={testUrl}
                  placeholder="https://hooks.example.com/…"
                  autocomplete="off"
                />
                <button
                  class="btn btn-sm btn-primary"
                  type="submit"
                  disabled={channelBusy !== null || !testUrl.trim()}
                >{channelBusy === `test:${profile.connector_id}` ? "Sending…" : "Send"}</button>
                <p class="note">
                  This runs the same governed path a real delivery takes: the capability gate,
                  the decision mode, the egress allowlist and the audit event all apply.
                </p>
              </form>
            {/if}
            {#if routingFor === profile.connector_id}
              <form class="channel-form routing-form" onsubmit={(event) => { event.preventDefault(); saveRouting(profile); }}>
                <div class="route-grid">
                  <label class="field-label" for={`route-${profile.connector_id}`}>Inbound</label>
                  <select id={`route-${profile.connector_id}`} class="input" bind:value={routeMode}>
                    <option value="record_only">Record only</option>
                    <option value="new_turn">New turn</option>
                    {#if profile.supports_side_questions}<option value="side_question">Side question</option>{/if}
                    {#if profile.supports_interrupts}<option value="interrupt">Interrupt or steer</option>{/if}
                  </select>
                  <label class="field-label" for={`owner-${profile.connector_id}`}>Owner sender</label>
                  <select id={`owner-${profile.connector_id}`} class="input" bind:value={routeOwner}>
                    <option value="">Not bound</option>
                    {#each profile.senders as sender}<option value={sender}>{sender}</option>{/each}
                  </select>
                  {#if routeMode === "side_question" || routeMode === "interrupt"}
                    <label class="field-label" for={`target-${profile.connector_id}`}>Conversation ID</label>
                    <input id={`target-${profile.connector_id}`} class="input" bind:value={routeTarget} placeholder="sess_…" autocomplete="off" />
                  {/if}
                </div>
                {#if profile.supports_approvals}
                  <label class="check-row">
                    <input type="checkbox" bind:checked={routeRelay} disabled={!routeOwner} />
                    <span>Allow exact pending approval responses from the bound owner</span>
                  </label>
                {/if}
                <div class="channel-actions">
                  <button class="btn btn-sm btn-primary" type="submit" disabled={channelBusy !== null}>Save routing</button>
                  <button class="btn btn-sm" type="button" onclick={() => (routingFor = null)}>Cancel</button>
                </div>
                <p class="note">
                  Record only is the default, and messages cannot choose their route. Side
                  questions have no tool budget; approvals require the exact relay and action
                  identity.
                  <GuideLink section="messaging" label="The routing contract" />
                </p>
              </form>
            {/if}
          {:else}
            <div class="channel-actions">
              <button
                type="button"
                class="btn btn-sm"
                disabled={channelBusy !== null}
                onclick={() => {
                  pairingFor = pairingFor === profile.connector_id ? null : profile.connector_id;
                  pairSenders = "";
                }}
              >Pair</button>
            </div>
            {#if pairingFor === profile.connector_id}
              <form
                class="channel-form"
                onsubmit={(event) => {
                  event.preventDefault();
                  pair(profile);
                }}
              >
                {#if profile.requires_sender_allowlist}
                  <label class="field-label" for={`senders-${profile.connector_id}`}>
                    Allowed senders
                  </label>
                  <input
                    id={`senders-${profile.connector_id}`}
                    class="input"
                    bind:value={pairSenders}
                    placeholder="one id per line, or comma-separated"
                    autocomplete="off"
                  />
                {/if}
                <button
                  class="btn btn-sm btn-primary"
                  type="submit"
                  disabled={channelBusy !== null}
                >{channelBusy === `pair:${profile.connector_id}` ? "Pairing…" : "Pair"}</button>
                <p class="note">
                  Pairing does not switch it on, and it does not trust anyone. Both are separate
                  decisions you make afterwards.
                </p>
              </form>
            {/if}
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .hook-list, .event-list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
  .hook-list > li, .event-list > li { display: grid; gap: 0.3rem; padding: var(--space-3); border: 1px solid var(--border); border-radius: var(--r-md); }
  .event-dead { opacity: 0.62; }
  .hook-tag { display: inline-flex; align-items: center; font-size: var(--text-2xs); font-weight: 650; padding: 0.05rem 0.5rem; border: 1px solid var(--accent-border); border-radius: var(--r-pill); background: var(--accent-soft); color: var(--accent); }
  .hook-tag-dead { border-color: var(--border); background: var(--sunken); color: var(--text-3); }
  .note { color: var(--text-3); font-size: var(--text-sm); }
  .channel-head { display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem; }
  .channel-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
  .channel-form { display: grid; gap: var(--space-2); margin-top: var(--space-2); }
  .channel-form label { display: grid; gap: 0.25rem; font-size: var(--text-sm); color: var(--text-2); }
  .notice { margin: 0 0 var(--space-3); padding: var(--space-3); border: 1px solid var(--border); border-radius: var(--r-md); }
  .notice-danger { border-color: var(--danger-border); background: var(--danger-soft); color: var(--danger); }
  .notice-ok { border-color: var(--ok-border); background: var(--ok-soft); color: var(--ok); }
  .card + .card { margin-top: var(--space-4); }
  .env { list-style: none; margin: var(--space-2) 0 0; padding: 0; display: grid; gap: var(--space-2); }
  .env li { display: grid; gap: 0.2rem; padding: var(--space-2); border-left: 2px solid var(--border); }
  .env li.env-missing { border-left-color: var(--warn); }
  .env code { font-size: var(--text-xs); }
</style>
