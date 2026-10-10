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
  import {
    ROUTE_LABELS,
    channelSteps,
    receiptConversationHref,
    receiptOutcome,
    receiptStages,
    receiptTitle,
    routeScopeFacts,
  } from "../channelSetup";
  import { relativeTime } from "../format";

  let channels = $state<ChannelsView | null>(null);
  let channelsError = $state<string | null>(null);
  let channelBusy = $state<string | null>(null);
  let channelNotice = $state<string | null>(null);
  let pairingFor = $state<string | null>(null);
  let pairSenders = $state("");
  let destinationFor = $state<string | null>(null);
  let destinationUrl = $state("");
  let sendersFor = $state<string | null>(null);
  let sendersDraft = $state("");
  let conversations = $state<{ session_id: string; title: string }[] | null>(null);
  let routingFor = $state<string | null>(null);
  let routeMode = $state<"record_only" | "new_turn" | "side_question" | "interrupt">("record_only");
  let routeTarget = $state("");
  let routeOwner = $state("");
  let routeRelay = $state(false);

  const CHANNEL_REASONS: Record<string, string> = {
    // §13.2 item 6 — another tab changed this channel since this page read it.
    channel_conflict:
      "This channel was changed somewhere else since this page loaded, so nothing was changed. It now shows the current settings.",
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
      "Choose which allowed sender is you before delivering to Telegram: a test goes to your chat.",
    channel_destination_missing: "Set where this channel delivers before sending a test.",
    channel_destination_invalid:
      "Use an https:// address, or http:// only to this machine or your own network, with no username or password in it.",
    channel_destination_not_configurable:
      "This channel delivers to your own chat, so there is no address to set.",
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
      // FIXED-719 — a refused action can still change what the server holds:
      // a refused test is recorded on the channel and as a receipt.
      await loadChannels();
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

  /**
   * UX-MSG-04 — a test names no destination. It goes where the channel
   * delivers: the webhook's bound URL, or your own chat on Telegram. The answer
   * is kept on the channel, so the checklist can count it, and as a receipt.
   */
  function sendTest(profile: ChannelProfile) {
    void runChannelAction(
      `test:${profile.connector_id}`,
      () => api.deliverChannelTest(profile.connector_id, "Raiker test delivery."),
      `Delivered a test to ${profile.display_label ?? profile.display_name}.`,
    );
  }

  function openDestination(profile: ChannelProfile) {
    destinationFor = destinationFor === profile.connector_id ? null : profile.connector_id;
    destinationUrl = "";
  }

  function saveDestination(profile: ChannelProfile) {
    void runChannelAction(
      `destination:${profile.connector_id}`,
      () => api.setChannelDestination(profile.pairing_id ?? "", destinationUrl.trim() || null, profile.revision),
      destinationUrl.trim()
        ? `${profile.display_name} delivers there now. Send a test to check it.`
        : `${profile.display_name} has no delivery address now.`,
    ).then(() => (destinationFor = null));
  }

  function openSenders(profile: ChannelProfile) {
    sendersFor = sendersFor === profile.connector_id ? null : profile.connector_id;
    sendersDraft = profile.senders.join(", ");
  }

  function saveSenders(profile: ChannelProfile) {
    const senders = sendersDraft
      .split(/[\n,]/)
      .map((entry) => entry.trim())
      .filter(Boolean);
    void runChannelAction(
      `senders:${profile.connector_id}`,
      () => api.setChannelSenders(profile.pairing_id ?? "", senders, profile.revision),
      `${profile.display_name} accepts ${senders.length} sender${senders.length === 1 ? "" : "s"}.`,
    ).then(() => (sendersFor = null));
  }

  /** UX-MSG-01 — the routed conversation is chosen by name, not typed as an id. */
  async function loadConversations() {
    if (conversations !== null) return;
    try {
      const rows = await api.sessions(undefined, false, "chat");
      conversations = rows.slice(0, 50).map((row) => ({
        session_id: row.session_id,
        title: row.title?.trim() || "Untitled conversation",
      }));
    } catch {
      conversations = [];
    }
  }

  /** The step the owner is on, so its control can open in place. */
  function stepAction(profile: ChannelProfile, step: string) {
    if (step === "owner" || step === "routing") openRouting(profile, true);
    else if (step === "senders") openSenders(profile);
    else if (step === "test") {
      if (profile.destination.kind === "url" && !profile.destination.configured) {
        openDestination(profile);
      } else sendTest(profile);
    }
  }

  function stepActionLabel(profile: ChannelProfile, step: string): string {
    if (step === "owner") return "Choose who you are";
    if (step === "senders") return "Edit senders";
    if (step === "routing") return "Change routing";
    if (step === "test") {
      return profile.destination.kind === "url" && !profile.destination.configured
        ? "Set delivery address"
        : "Send a test";
    }
    if (step === "enabled") return "Turn on";
    return "";
  }

  function openRouting(profile: ChannelProfile, keepOpen = false) {
    routingFor =
      routingFor === profile.connector_id && !keepOpen ? null : profile.connector_id;
    void loadConversations();
    routeMode = profile.routing_mode ?? "record_only";
    routeTarget = profile.target_session_id ?? "";
    routeOwner = profile.owner_sender_id ?? "";
    routeRelay = profile.approval_relay_enabled ?? false;
  }

  function routeLabel(mode: ChannelProfile["routing_mode"]): string {
    return ROUTE_LABELS[mode] ?? ROUTE_LABELS.record_only;
  }

  function saveRouting(profile: ChannelProfile) {
    void runChannelAction(
      `routing:${profile.connector_id}`,
      () => api.setChannelRouting(profile.pairing_id ?? "", {
        routing_mode: routeMode,
        target_session_id: routeTarget.trim() || null,
        owner_sender_id: routeOwner.trim() || null,
        approval_relay_enabled: routeRelay,
      }, profile.revision),
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

<section class="card" data-testid="channel-profiles">
  <!-- REM-MSG-02 — one name for the thing an owner connects. The page called
       the same object a Channel in one heading and a Connector in the next, so
       "pair the connector" and "turn on the channel" read as two objects with
       two lifecycles. Channels is the user-facing name; the connector id stays
       internal, and the extension behind it is a link for diagnostics. -->
  <h2>Channels</h2>
  <p class="note">
    A channel message is <strong>untrusted content with a named sender who is not you</strong>,
    and cannot raise a turn's authority. Linked, enabled, trusted and reachable are separate —
    each channel says which of them it has. The extension behind one is in
    <a href="#/extensions?tab=connectors">Extensions → Connectors</a>.
  </p>
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
              {profile.linked
                ? profile.enabled
                  ? profile.paused
                    ? "Paused"
                    : "On"
                  : "Linked, off"
                : "Not linked"}
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
          {#if !profile.linked}
            <p class="next-step">{channelSteps(profile)[0].detail}</p>
          {/if}

          <!-- What this transport needs from the environment, declared on the
               connector profile rather than left to the guide. It answers the
               question an owner actually has in front of a channel that will
               not send — *which variable, and is it set*. Whether, never what:
               Raiker takes the name of a variable and never its value, and that
               holds on this surface too. -->
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
            <!-- UX-MSG-03 — the order is the contract. Connected → owner verified
                 → allowed senders → routing → test → on, each a fact the server
                 reports, the first unfinished one carrying its own control. -->
            <ol class="setup-steps" aria-label={`${profile.display_name} setup`}>
              {#each channelSteps(profile) as step (step.id)}
                <li class={`step step-${step.state}`} aria-current={step.state === "current" ? "step" : undefined}>
                  <span class="step-mark" aria-hidden="true">
                    {step.state === "done" ? "✓" : step.state === "not_needed" ? "–" : ""}
                  </span>
                  <span class="step-body">
                    <strong>{step.label}</strong>
                    <span class="step-state">
                      {step.state === "done"
                        ? "Done"
                        : step.state === "current"
                          ? "Next"
                          : step.state === "not_needed"
                            ? "Not needed"
                            : "To do"}
                    </span>
                    <span class="step-detail">{step.detail}</span>
                    {#if step.state === "current" && step.id !== "enabled" && stepActionLabel(profile, step.id)}
                      <button
                        type="button"
                        class="btn btn-sm btn-primary step-action"
                        disabled={channelBusy !== null}
                        onclick={() => stepAction(profile, step.id)}
                      >{channelBusy === `test:${profile.connector_id}` && step.id === "test"
                          ? "Sending…"
                          : stepActionLabel(profile, step.id)}</button>
                    {/if}
                  </span>
                </li>
              {/each}
            </ol>

            <div class="channel-actions">
              <button
                type="button"
                class="btn btn-sm"
                class:btn-primary={!profile.enabled && channelSteps(profile).find((step) => step.state === "current")?.id === "enabled"}
                disabled={channelBusy !== null}
                onclick={() =>
                  void runChannelAction(
                    `enable:${profile.pairing_id}`,
                    () => api.setChannelEnabled(profile.pairing_id ?? "", !profile.enabled, profile.revision),
                    profile.enabled
                      ? `${profile.display_name} is off.`
                      : `${profile.display_name} is on.`,
                  )}
              >{profile.enabled ? "Turn off" : "Turn on"}</button>
              <!-- DEC-14 step 10 — contain without losing anything: paused keeps
                   receiving and recording, and starts and sends nothing. -->
              {#if profile.enabled}
                <button
                  type="button"
                  class="btn btn-sm"
                  disabled={channelBusy !== null}
                  onclick={() =>
                    void runChannelAction(
                      `pause:${profile.pairing_id}`,
                      () => api.setChannelPaused(profile.pairing_id ?? "", !profile.paused, profile.revision),
                      profile.paused
                        ? `${profile.display_name} is acting on messages again.`
                        : `${profile.display_name} is paused. Messages are kept; nothing starts and nothing is sent.`,
                    )}
                >{profile.paused ? "Resume" : "Pause"}</button>
              {/if}
              {#if profile.destination.kind !== "none"}
                <button
                  type="button"
                  class="btn btn-sm"
                  disabled={channelBusy !== null ||
                    (profile.destination.kind === "url" && !profile.destination.configured)}
                  onclick={() => sendTest(profile)}
                >Send a test delivery</button>
              {/if}
              {#if profile.destination.kind === "url"}
                <button
                  type="button"
                  class="btn btn-sm"
                  disabled={channelBusy !== null}
                  onclick={() => openDestination(profile)}
                  aria-expanded={destinationFor === profile.connector_id}
                >Delivery address</button>
              {/if}
              {#if profile.requires_sender_allowlist}
                <button
                  type="button"
                  class="btn btn-sm"
                  disabled={channelBusy !== null}
                  onclick={() => openSenders(profile)}
                  aria-expanded={sendersFor === profile.connector_id}
                >Senders</button>
              {/if}
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
                    () => api.unpairChannel(profile.pairing_id ?? "", profile.revision),
                    `${profile.display_name} is unpaired. Nothing can reach it now.`,
                  )}
              >Unpair</button>
            </div>
            <p class="note">
              {#if profile.destination.kind === "url"}
                {#if profile.destination.configured}
                  Delivers to <strong>{profile.destination.host}</strong>{profile.destination.allowlisted
                    ? "."
                    : " — not on the channel egress allowlist, so a delivery is refused before it leaves."}
                {:else}
                  No delivery address yet.
                {/if}
              {:else if profile.destination.kind === "owner_chat"}
                Delivers to your own chat{profile.owner_sender_id ? "" : ", once you choose which sender is you"}.
              {:else}
                This build cannot deliver over this channel.
              {/if}
              A test runs the same governed path a real delivery takes: the capability gate, the
              decision mode, the egress allowlist and the audit event all apply.
            </p>

            {#if destinationFor === profile.connector_id}
              <form
                class="channel-form"
                onsubmit={(event) => {
                  event.preventDefault();
                  saveDestination(profile);
                }}
              >
                <label class="field-label" for={`destination-${profile.connector_id}`}>
                  Delivery address
                </label>
                <input
                  id={`destination-${profile.connector_id}`}
                  class="input"
                  bind:value={destinationUrl}
                  placeholder="https://hooks.example.com/…"
                  autocomplete="off"
                />
                <div class="channel-actions">
                  <button class="btn btn-sm btn-primary" type="submit" disabled={channelBusy !== null}>
                    {destinationUrl.trim() ? "Save address" : "Clear address"}
                  </button>
                  <button class="btn btn-sm" type="button" onclick={() => (destinationFor = null)}>Cancel</button>
                </div>
                <p class="note">
                  Every delivery on this channel goes here, tests included; nothing can name another
                  address. Use https://, or http:// only to this machine or your own network. Changing
                  it forgets the last test.
                </p>
              </form>
            {/if}
            {#if sendersFor === profile.connector_id}
              <form
                class="channel-form"
                onsubmit={(event) => {
                  event.preventDefault();
                  saveSenders(profile);
                }}
              >
                <label class="field-label" for={`edit-senders-${profile.connector_id}`}>
                  Allowed senders
                </label>
                <input
                  id={`edit-senders-${profile.connector_id}`}
                  class="input"
                  bind:value={sendersDraft}
                  placeholder="one id per line, or comma-separated"
                  autocomplete="off"
                />
                <div class="channel-actions">
                  <button class="btn btn-sm btn-primary" type="submit" disabled={channelBusy !== null}>Save senders</button>
                  <button class="btn btn-sm" type="button" onclick={() => (sendersFor = null)}>Cancel</button>
                </div>
                <p class="note">Anyone not listed is refused and recorded. Allowed is not trusted.</p>
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
                  <label class="field-label" for={`owner-${profile.connector_id}`}>You on this channel</label>
                  <select id={`owner-${profile.connector_id}`} class="input" bind:value={routeOwner}>
                    <option value="">Not chosen</option>
                    {#each profile.senders as sender}<option value={sender}>{sender}</option>{/each}
                  </select>
                  {#if routeMode !== "record_only"}
                    <label class="field-label" for={`target-${profile.connector_id}`}>Conversation</label>
                    <select id={`target-${profile.connector_id}`} class="input" bind:value={routeTarget}>
                      {#if routeMode === "new_turn"}
                        <option value="">A new conversation for each message</option>
                      {:else}
                        <option value="">Choose a conversation…</option>
                      {/if}
                      {#if routeTarget && !(conversations ?? []).some((row) => row.session_id === routeTarget)}
                        <option value={routeTarget}>{profile.target_session_title ?? "The current conversation"}</option>
                      {/if}
                      {#each conversations ?? [] as row (row.session_id)}
                        <option value={row.session_id}>{row.title}</option>
                      {/each}
                    </select>
                  {/if}
                </div>
                {#if profile.supports_approvals}
                  <label class="check-row">
                    <input type="checkbox" bind:checked={routeRelay} disabled={!routeOwner} />
                    <span>Allow exact pending approval responses from you on this channel</span>
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

            <!-- UX-MSG-05 — the stored route as what the receiver does with it,
                 stated by the server so the page cannot claim a scope nothing
                 enforces. -->
            <details class="route-scope">
              <summary>What this route does · {routeLabel(profile.routing_mode)}</summary>
              <dl>
                {#each routeScopeFacts(profile.route_scope) as fact (fact.label)}
                  <dt>{fact.label}</dt>
                  <dd>{fact.value}</dd>
                {/each}
              </dl>
            </details>

            <!-- UX-MSG-06 — received, accepted, queued, processed, reply queued,
                 delivered and failed are separate facts, so a finished turn is
                 never read as a delivered reply. -->
            <section class="receipts" aria-label={`${profile.display_name} recent activity`}>
              <h3>Recent activity</h3>
              {#if profile.receipts.length === 0}
                <p class="note">Nothing yet. Tests and messages appear here, each stage as it happens.</p>
              {:else}
                <ul>
                  {#each profile.receipts as receipt (receipt.receipt_id)}
                    <li>
                      <span class="receipt-head">
                        <strong>{receiptTitle(receipt)}</strong>
                        <span class="note">{relativeTime(receipt.created_at)}</span>
                      </span>
                      <span class="receipt-stages">
                        {#each receiptStages(receipt) as stage (stage)}
                          <span class="hook-tag" class:hook-tag-failed={stage === "failed"}>{stage}</span>
                        {/each}
                      </span>
                      <span class="note">
                        {receiptOutcome(receipt)}
                        {#if receiptConversationHref(receipt)}
                          · <a href={receiptConversationHref(receipt)}>Open the conversation</a>
                        {/if}
                      </span>
                    </li>
                  {/each}
                </ul>
              {/if}
            </section>
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

<!-- REM-MSG-01 — the operator's environment, below the channels rather than
     in front of them. These five rows are process configuration read back:
     which variable is set, what an empty one refuses. They are real and they
     are kept, and they were the first thing an owner met on this page — so
     connecting a messaging account began with a briefing on HMAC signing and
     an inbound secret. -->
<details class="card advanced" data-testid="channel-posture">
  <summary>Delivery environment</summary>
  <p class="note">
    Set outside this app, in the host process. Raiker reads whether each variable is set and
    never its value.
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
</details>


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
  /* The first step, for a channel that is not paired yet. */
  .next-step { margin: 0.2rem 0 0; color: var(--text-2); font-size: var(--text-sm); }
  /* UX-MSG-03 — the setup checklist. */
  .setup-steps { list-style: none; margin: var(--space-2) 0 0; padding: 0; display: grid; gap: 0.35rem; }
  .step { display: grid; grid-template-columns: 1.4rem minmax(0, 1fr); gap: var(--space-2); align-items: start; }
  .step-mark { display: inline-grid; place-items: center; width: 1.25rem; height: 1.25rem; border-radius: 50%; border: 1px solid var(--border); font-size: var(--text-2xs); font-weight: 700; color: var(--text-3); }
  .step-done .step-mark { border-color: var(--ok-border); background: var(--ok-soft); color: var(--ok); }
  .step-current .step-mark { border-color: var(--accent); background: var(--accent-soft); }
  .step-body { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.2rem 0.5rem; min-width: 0; }
  .step-state { font-size: var(--text-2xs); font-weight: 650; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.04em; }
  .step-current .step-state { color: var(--accent); }
  .step-detail { flex-basis: 100%; color: var(--text-2); font-size: var(--text-sm); overflow-wrap: anywhere; }
  .step-todo .step-detail, .step-not_needed .step-detail { color: var(--text-3); }
  .step-action { margin-top: 0.15rem; }
  /* UX-MSG-05 / UX-MSG-06 */
  .route-scope { margin-top: var(--space-2); font-size: var(--text-sm); }
  .route-scope summary { cursor: pointer; color: var(--text-2); font-weight: 650; }
  .route-scope dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 0.25rem var(--space-3); margin: var(--space-2) 0 0; }
  .route-scope dt { color: var(--text-3); }
  .route-scope dd { margin: 0; color: var(--text-2); }
  .receipts { margin-top: var(--space-2); }
  .receipts h3 { margin: 0 0 0.3rem; font-size: var(--text-sm); color: var(--text-2); }
  .receipts ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.4rem; }
  .receipts li { display: grid; gap: 0.15rem; padding: 0.4rem 0; border-top: 1px solid var(--border); }
  .receipt-head { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: baseline; }
  .receipt-stages { display: flex; flex-wrap: wrap; gap: 0.3rem; }
  .hook-tag-failed { border-color: var(--danger-border); background: var(--danger-soft); color: var(--danger); }
  @media (max-width: 560px) {
    .route-scope dl { grid-template-columns: minmax(0, 1fr); }
    .route-scope dd { margin-bottom: 0.3rem; }
  }
  .advanced summary { cursor: pointer; color: var(--text-2); font-weight: 650; }
  .env code { font-size: var(--text-xs); }
</style>