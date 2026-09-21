<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../../components/Icon.svelte";
  import { api } from "../../api";
  import type { UpdateStatusView } from "../../apiTypes";
  import { clientBuild, clientIsStale, describeBuild } from "../../buildIdentity";

  let update = $state<UpdateStatusView | null>(null);
  let busy = $state<"checking" | "applying" | null>(null);
  let notice = $state<string | null>(null);
  let confirm = $state(false);

  /**
   * The states, named as the different things they are.
   *
   * REM-SET-UPDATES — the page printed only the backend's sentence, so an
   * installation nobody had ever checked and one confirmed current a minute ago
   * both read as a paragraph of reassuring prose. Offered, verified, installed
   * and restart-required are not the same state, and the first of them is as far
   * as a *check* can get.
   */
  const STATE_LABELS: Record<string, string> = {
    source_checkout: "Not an installed release",
    no_channel: "No channel pinned",
    unsigned_build: "Unsigned build — not eligible",
    not_checked: "Not checked yet",
    up_to_date: "Checked — nothing newer offered",
    available: "A newer release is offered",
    unreachable: "Channel unreachable — unknown",
  };

  /**
   * GCR-16 — the build identity, said once and in one place.
   *
   * "Installed version" was the only thing this page said about which Raiker
   * this is, and it was one of four numbers that disagreed. It now names the
   * commit the artifact was built from and when it was built, and it names the
   * build of the page reading it, because a browser holding a bundle cached from
   * before an update is exactly the state neither number describes on its own.
   */
  const buildLabel = $derived(
    update === null
      ? ""
      : describeBuild(update.installation.version, update.installation.commit),
  );
  const builtLabel = $derived(
    update === null || update.installation.built_at === null
      ? "Not recorded"
      : new Date(update.installation.built_at).toLocaleString(),
  );
  const stale = $derived(update !== null && clientIsStale(update.installation.version));

  const checkedLabel = $derived(
    update === null || update.checked_at === null
      ? "Never on this host"
      : new Date(update.checked_at).toLocaleString(),
  );

  async function load() {
    try { update = await api.hostUpdate(); }
    catch { notice = "Update status could not be read."; }
  }
  async function check() {
    busy = "checking"; notice = null;
    try { update = await api.checkHostUpdate(); notice = update.message; }
    catch { notice = "The update check could not be carried out."; }
    finally { busy = null; }
  }
  async function apply() {
    busy = "applying"; notice = null;
    try {
      const result = await api.applyHostUpdate(confirm);
      update = result;
      if (result.ok) {
        /*
         * REM-SET-UPDATES — what this response actually establishes is that a
         * detached helper was started. It said "Installing …", which is a claim
         * about an installation that has not begun: the helper waits for this
         * process to exit before it re-checks the channel, verifies the bundle
         * and replaces any files. An owner who reads "Installing" and then
         * force-quits believes they interrupted an install rather than a
         * handover.
         */
        notice =
          `The verified update helper for ${result.version} has started. Raiker will close, ` +
          "and the helper verifies the signed bundle before it replaces anything. " +
          "Nothing on this installation has changed yet.";
      } else if (result.reason_code === "waiting_work") {
        confirm = true;
        notice = "An update would interrupt work in progress. Select Update and restart again to confirm.";
      } else notice = result.message;
    } catch { notice = "The verified update could not be started."; }
    finally { busy = null; }
  }
  onMount(load);
</script>

<header class="section-heading"><h2>Updates</h2></header>
<section class="settings-card" aria-label="Raiker updates">
  <div class="card-heading"><span class="eyebrow">Application</span><h3>Signed updates</h3></div>
  {#if update === null}
    <p class="description">Loading update status…</p>
  {:else}
    <p class="description">{update.message}</p>
    <dl>
      <div><dt>Installed build</dt><dd>{buildLabel}</dd></div>
      <div><dt>Built</dt><dd>{builtLabel}</dd></div>
      <div>
        <dt>This page</dt>
        <dd>
          {clientBuild === update.installation.version ? "Same build" : describeBuild(clientBuild, null)}
        </dd>
      </div>
      <div><dt>Channel</dt><dd>{update.channel ? update.channel.channel : "Not configured"}</dd></div>
      {#if update.recovery_points.length}<div><dt>Recovery</dt><dd>{update.recovery_points.map((point) => point.version).join(", ")}</dd></div>{/if}
      <!-- The licence was permanent prose at the foot of the
           navigation rail. It is a fact about the installation, read once, and
           this is where the rest of the facts about the installation are. -->
      <div><dt>Licence</dt><dd>Apache License, Version 2.0</dd></div>
    </dl>
    <!-- REM-SET-UPDATES — five different states, said as five different
         things. `Checked` is the one an owner cannot get from anywhere else:
         without it, "This is the newest release" reads the same whether it was
         confirmed a minute ago or never asked at all. -->
    <dl>
      <div>
        <dt>Update state</dt>
        <dd>{STATE_LABELS[update.state] ?? update.state}</dd>
      </div>
      <div>
        <dt>Channel last checked</dt>
        <dd>{checkedLabel}</dd>
      </div>
    </dl>
    {#if stale}
      <p class="notice" role="status">
        This page was loaded from an older build than the one now running. Reload
        Raiker so the page and the host are the same release.
      </p>
    {/if}
    {#if update.available}
      <p class="description">
        Version {update.available.version} is offered on the channel. Nothing has been downloaded
        yet: Raiker verifies the release metadata and the bundle's signature during the update,
        and replaces files only if both verify.
      </p>
      <button class="btn btn-primary" type="button" disabled={busy !== null} onclick={() => void apply()}>
        <Icon name="refresh" size="sm" /> {busy === "applying" ? "Starting update…" : confirm ? "Confirm update and restart" : "Update and restart"}
      </button>
    {/if}
  {/if}
  <button class="btn btn-ghost btn-sm" type="button" disabled={busy !== null} onclick={() => void check()}>
    <Icon name="refresh" size="sm" /> {busy === "checking" ? "Checking…" : "Check for updates"}
  </button>
  {#if notice}<p class="notice" role="status">{notice}</p>{/if}
</section>
