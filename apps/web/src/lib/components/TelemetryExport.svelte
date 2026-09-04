<script lang="ts">
  /**
   * Backlog #18 — the governed record, on a wire.
   *
   * Raiker keeps more per action than any compared product exports and had
   * nowhere to send it. This is where an owner names a collector and runs a
   * delivery. It is deliberately small: a list, a form behind a disclosure, and
   * one sentence saying what a record carries.
   *
   * The credential is a *name*. The form takes the name of an environment
   * variable holding an `Authorization` value and never the value, so a
   * credential cannot be typed into a browser field and stored.
   */
  import { onMount } from "svelte";
  import Icon from "./Icon.svelte";
  import { api, ApiError } from "../api";
  import { runtimeBlock } from "../capabilityModel";
  import { relativeFuture, relativeTime } from "../format";
  import type { CapabilityGate, TelemetryDestination } from "../apiTypes";

  let destinations = $state<TelemetryDestination[] | null>(null);
  // A delivery leaves the machine, so it answers to `telemetry_export` like
  // every other Tier-2 capability. A closed gate returned the raw
  // `disabled_by_capability_gate` from the Deliver button — a code where a
  // sentence and a route belong, which is the FIXED-370 defect in miniature.
  // Said before the press instead, through the same helper every other surface
  // uses, so this page cannot word it differently from the rest of them.
  let gates = $state<CapabilityGate[]>([]);
  const block = $derived(
    runtimeBlock(
      gates.find((gate) => gate.capability === "telemetry_export"),
      "Telemetry export",
    ),
  );
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let busy = $state<string | null>(null);
  let adding = $state(false);

  let name = $state("");
  let endpoint = $state("");
  let headerRef = $state("");
  let includeContent = $state(false);

  function reason(e: unknown): string {
    if (e instanceof ApiError) return e.reasonCode ?? `Request failed (${e.status})`;
    return "Request failed";
  }

  async function load() {
    error = null;
    try {
      destinations = await api.telemetryDestinations();
    } catch (e) {
      destinations = [];
      error = reason(e);
    }
    // A failed gate read must not take the section down with it: the
    // destinations are still readable and still worth showing.
    try {
      gates = await api.capabilityGates();
    } catch {
      gates = [];
    }
  }

  async function add(event: SubmitEvent) {
    event.preventDefault();
    busy = "create";
    error = null;
    notice = null;
    try {
      await api.createTelemetryDestination({
        name: name.trim(),
        endpoint_url: endpoint.trim(),
        header_ref: headerRef.trim(),
        include_content: includeContent,
      });
      name = "";
      endpoint = "";
      headerRef = "";
      includeContent = false;
      adding = false;
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  async function run(destination: TelemetryDestination) {
    busy = destination.destination_id;
    error = null;
    notice = null;
    try {
      const result = await api.runTelemetryExport(destination.destination_id);
      notice = `${destination.name}: ${result.exported} event(s) delivered.`;
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  /**
   * BUG-276 — a card must never let you believe events are flowing when
   * nothing has run since you last pressed the button. Either it names the
   * cadence it is delivered on, or it says it is on demand only.
   */
  const CADENCES: readonly { id: string; label: string }[] = [
    { id: "off", label: "On demand only" },
    { id: "continuous", label: "Every 20 minutes" },
    { id: "hourly", label: "Hourly" },
    { id: "daily", label: "Daily" },
    { id: "weekly", label: "Weekly" },
  ];

  function cadenceLabel(id: string): string {
    // An unrecognised cadence is shown verbatim rather than read as "off": a
    // schedule this build does not know is still a schedule the host is running.
    return CADENCES.find((c) => c.id === id)?.label ?? `Every ${id}`;
  }

  async function setCadence(destination: TelemetryDestination, cadence: string) {
    if (cadence === destination.delivery_cadence) return;
    busy = destination.destination_id;
    error = null;
    notice = null;
    try {
      await api.setTelemetryCadence(destination.destination_id, cadence);
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  /**
   * BUG-283 — what the last delivery did, as a sentence.
   *
   * The row printed `d.last_status` verbatim, so a failed run read
   * `telemetry_delivery_failed:fetch_failed:URLError` on the page. That was
   * survivable while delivery only happened when somebody pressed the button and
   * watched the result; putting destinations on a cadence (FIXED-386) made an
   * unattended failure the ordinary case, so the raw code is now what an owner
   * meets on a page they were not looking at when it happened.
   *
   * Same rule as everywhere else in this product: a reason code is the audit
   * vocabulary, and a surface says what it means. The code is kept in `title` so
   * it is still one hover away for correlating against the log.
   */
  function statusLine(status: string | null): string {
    if (!status) return "Never run";
    if (status === "ok") return "Last run ok";
    if (status === "telemetry_credential_missing")
      return "Last run refused: the credential variable is unset";
    if (status === "telemetry_destination_disabled") return "Last run refused: destination off";
    if (status.startsWith("telemetry_rejected_"))
      return `Last run refused by the collector (${status.slice("telemetry_rejected_".length)})`;
    if (status.includes("fetch_failed")) return "Last run could not reach the collector";
    if (status.includes("http_error"))
      return `Last run was rejected (${status.slice(status.lastIndexOf("_") + 1)})`;
    return "Last run did not complete";
  }

  async function remove(destination: TelemetryDestination) {
    if (!confirm(`Remove “${destination.name}”? Nothing already delivered is affected.`)) return;
    busy = destination.destination_id;
    error = null;
    try {
      await api.deleteTelemetryDestination(destination.destination_id);
      await load();
    } catch (e) {
      error = reason(e);
    } finally {
      busy = null;
    }
  }

  onMount(load);
</script>

<section aria-labelledby="otlp-h" class="otlp">
  <h2 id="otlp-h" class="section-h">Can I see this outside Raiker?</h2>
  <p>
    Governed events go to an OpenTelemetry collector as identifiers and an event type — on a
    cadence, or on demand. Content is off unless a destination opts in, and is redacted the same
    way this screen is.
  </p>

  {#if block.kind !== "none"}
    <p class="notice" role="status">
      {block.reason}
      {#if block.href}<a href={block.href}>{block.linkLabel}</a>{/if}
    </p>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if notice}<p class="notice" role="status">{notice}</p>{/if}

  {#if destinations !== null && destinations.length}
    <ul class="list">
      {#each destinations as d (d.destination_id)}
        <li>
          <div class="row">
            <span class="name">{d.name}</span>
            <code>{d.endpoint_url}</code>
            <span class="tag">{d.include_content ? "With redacted content" : "Metadata only"}</span>
          </div>
          <div class="row muted">
            <span>{d.exported_count} delivered</span>
            {#if d.last_attempt_at}
              <span title={d.last_status ?? ""}
                >{statusLine(d.last_status)} · {relativeTime(d.last_attempt_at)}</span
              >
            {:else}
              <span>Never run</span>
            {/if}
            {#if d.delivery_cadence !== "off" && d.next_delivery_at}
              <span>Next {relativeFuture(d.next_delivery_at)}</span>
            {/if}
            {#if d.header_ref}<span>Credential: ${d.header_ref}</span>{/if}
          </div>
          <div class="row">
            <label class="cadence">
              <span class="sr-only">Delivery cadence for {d.name}</span>
              <select
                value={d.delivery_cadence}
                onchange={(e) => setCadence(d, (e.currentTarget as HTMLSelectElement).value)}
                disabled={busy !== null || block.kind !== "none"}
              >
                {#each CADENCES as c (c.id)}
                  <option value={c.id}>{c.label}</option>
                {/each}
                {#if !CADENCES.some((c) => c.id === d.delivery_cadence)}
                  <option value={d.delivery_cadence}>{cadenceLabel(d.delivery_cadence)}</option>
                {/if}
              </select>
            </label>
            <button
              type="button"
              class="btn btn-sm"
              onclick={() => run(d)}
              disabled={busy !== null || block.kind !== "none"}
            >
              {busy === d.destination_id ? "Delivering…" : "Deliver now"}
            </button>
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              onclick={() => remove(d)}
              disabled={busy !== null}
            >
              Remove
            </button>
          </div>
        </li>
      {/each}
    </ul>
  {:else if destinations !== null}
    <p class="muted">No collector yet.</p>
  {/if}

  {#if adding}
    <form onsubmit={add} class="add">
      <label>
        Name
        <input bind:value={name} required placeholder="Local collector" />
      </label>
      <label>
        OTLP endpoint
        <input bind:value={endpoint} required placeholder="http://127.0.0.1:4318" />
      </label>
      <label>
        Credential variable
        <input bind:value={headerRef} placeholder="OTEL_AUTH_HEADER (optional)" />
      </label>
      <label class="check">
        <input type="checkbox" bind:checked={includeContent} />
        Send redacted event payloads too
      </label>
      <div class="row">
        <button type="submit" class="btn btn-sm" disabled={busy === "create"}>
          {busy === "create" ? "Adding…" : "Add collector"}
        </button>
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => (adding = false)}>
          Cancel
        </button>
      </div>
    </form>
  {:else}
    <button type="button" class="btn btn-sm" onclick={() => (adding = true)}>
      <Icon name="globe" size={15} /> Add collector
    </button>
  {/if}
</section>

<style>
  /* The four sections above this one are styled by ObserveView, whose CSS is
     scoped to that file — so a heading given the same class here inherited
     nothing and rendered a size larger than its siblings. Matched rather than
     hoisted: one component owning one heading is the smaller change. */
  .otlp .section-h { font-size: 0.95rem; margin: 0 0 var(--space-3); }
  .otlp p { margin: 0 0 var(--space-3); color: var(--text-2); max-width: 68ch; }
  .list { list-style: none; margin: 0 0 var(--space-3); padding: 0; display: grid; gap: var(--space-3); }
  .list li { border: 1px solid var(--border); border-radius: var(--r-md); padding: var(--space-3); display: grid; gap: 0.35rem; }
  .row { display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap; }
  .name { font-weight: 600; }
  .muted { color: var(--text-3); font-size: var(--text-sm); }
  .tag { font-size: 0.72rem; color: var(--text-3); border: 1px solid var(--border); border-radius: 999px; padding: 0.05rem 0.5rem; }
  .cadence select { font-size: 0.78rem; padding: 0.2rem 0.4rem; }
  .error { color: var(--danger); }
  .notice { color: var(--text-2); }
  .notice a { margin-left: 0.35rem; }
  .add { display: grid; gap: var(--space-3); max-width: 32rem; }
  .add label { display: grid; gap: 0.25rem; font-size: 0.8rem; color: var(--text-2); }
  .add .check { display: flex; align-items: center; gap: 0.5rem; }
  code { font-size: 0.78rem; color: var(--text-3); word-break: break-all; }
</style>
