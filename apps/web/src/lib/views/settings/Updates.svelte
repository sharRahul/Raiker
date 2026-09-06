<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "../../components/Icon.svelte";
  import { api } from "../../api";
  import type { UpdateStatusView } from "../../apiTypes";

  let update = $state<UpdateStatusView | null>(null);
  let busy = $state<"checking" | "applying" | null>(null);
  let notice = $state<string | null>(null);
  let confirm = $state(false);

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
      if (result.ok) notice = `Installing ${result.version}. Raiker will close and restart shortly.`;
      else if (result.reason_code === "waiting_work") {
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
      <div><dt>Installed version</dt><dd>{update.installation.version}</dd></div>
      <div><dt>Channel</dt><dd>{update.channel ? update.channel.channel : "Not configured"}</dd></div>
      {#if update.recovery_points.length}<div><dt>Recovery</dt><dd>{update.recovery_points.map((point) => point.version).join(", ")}</dd></div>{/if}
      <!-- VIS2-02 — the licence was permanent prose at the foot of the
           navigation rail. It is a fact about the installation, read once, and
           this is where the rest of the facts about the installation are. -->
      <div><dt>Licence</dt><dd>Apache License, Version 2.0</dd></div>
    </dl>
    {#if update.available}
      <p class="description">Version {update.available.version} is ready to install. Its release metadata and bundle are verified before Raiker replaces files.</p>
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
