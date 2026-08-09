<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../../api";
  import type { ModelOperation } from "../../apiTypes";
  let items = $state<ModelOperation[]>([]);
  let error = $state<string | null>(null);
  const terminal = (state: string) =>
    ["complete", "failed", "cancelled"].includes(state);
  async function load() {
    try {
      items = (await api.modelOperations()).items;
      error = null;
    } catch {
      error = "Could not load model activity.";
    }
  }
  async function cancel(id: string) {
    await api.cancelModelOperation(id);
    await load();
  }
  async function retry(id: string) {
    await api.retryModelOperation(id);
    await load();
  }
  async function cleanup(id: string) {
    await api.cleanupModelOperation(id);
    await load();
  }
  onMount(() => {
    void load();
    const interval = window.setInterval(() => void load(), 1_000);
    return () => window.clearInterval(interval);
  });
</script>

<section class="activity" aria-labelledby="activity-title">
  <header>
    <div>
      <p class="eyebrow">Durable operations</p>
      <h2 id="activity-title">Downloads and model jobs</h2>
      <p>
        Jobs survive navigation and interrupted app sessions. Failed work is
        never silently retried.
      </p>
    </div>
    <button class="btn btn-ghost" type="button" onclick={load}>Refresh</button>
  </header>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if items.length === 0}<div class="empty">
      <strong>No model activity yet</strong><span
        >Downloads, conversions, runtime installs, pulls, and deployments appear
        here.</span
      >
    </div>
  {:else}<div class="timeline">
      {#each items as item (item.operation_id)}<article>
          <div
            class="rail"
            class:done={item.state === "complete"}
            class:failed={item.state === "failed"}
          ></div>
          <div class="job">
            <div class="job-head">
              <div>
                <span class="kind">{item.kind}</span>
                <h3>{item.target}</h3>
              </div>
              <strong class:bad={item.state === "failed"}
                >{item.state.replaceAll("_", " ")}</strong
              >
            </div>
            <p>
              {item.phase.replaceAll("_", " ")}{#if item.error_code}
                · {item.error_code.replaceAll("_", " ")}{/if}
            </p>
            {#if item.progress_percent !== null}<div
                class="progress"
                aria-label={`${item.progress_percent}% complete`}
              >
                <span style={`width:${item.progress_percent}%`}></span>
              </div>{/if}
            <div class="actions">
              {#if !terminal(item.state)}<button
                  class="btn btn-ghost btn-sm"
                  type="button"
                  onclick={() => void cancel(item.operation_id)}>Cancel</button
                >{:else if item.state === "failed"}<button
                  class="btn btn-sm"
                  type="button"
                  onclick={() => void retry(item.operation_id)}>Retry</button
                >{/if}{#if terminal(item.state)}<button
                  class="btn btn-ghost btn-sm"
                  type="button"
                  onclick={() => void cleanup(item.operation_id)}
                  >Clear record</button
                >{/if}
            </div>
          </div>
        </article>{/each}
    </div>{/if}
</section>

<style>
  .activity {
    --text-muted: var(--text-2);
    display: grid;
    gap: 18px;
  }
  .activity > header {
    display: flex;
    justify-content: space-between;
    gap: 20px;
  }
  .activity h2 {
    margin: 2px 0 6px;
  }
  .activity header p {
    margin: 0;
    color: var(--text-muted);
  }
  .empty {
    display: grid;
    place-items: center;
    gap: 6px;
    padding: 64px 20px;
    border: 1px dashed var(--border);
    border-radius: 14px;
    color: var(--text-muted);
  }
  .timeline {
    display: grid;
  }
  .timeline article {
    display: grid;
    grid-template-columns: 18px 1fr;
    gap: 12px;
  }
  .rail {
    width: 3px;
    height: 100%;
    min-height: 110px;
    background: var(--border);
    position: relative;
  }
  .rail:before {
    content: "";
    position: absolute;
    left: -5px;
    top: 5px;
    width: 13px;
    height: 13px;
    border-radius: 50%;
    background: #d97706;
    border: 3px solid var(--surface);
  }
  .rail.done:before {
    background: #15803d;
  }
  .rail.failed:before {
    background: #b91c1c;
  }
  .job {
    padding: 0 0 24px;
  }
  .job-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }
  .job h3 {
    margin: 3px 0;
  }
  .job p {
    color: var(--text-muted);
    margin: 5px 0;
  }
  .kind {
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.7rem;
    font-weight: 750;
  }
  .bad {
    color: #b91c1c;
  }
  .progress {
    height: 5px;
    background: var(--border);
    margin: 12px 0;
    border-radius: 4px;
    overflow: hidden;
  }
  .progress span {
    display: block;
    height: 100%;
    background: #2563eb;
  }
  .actions {
    display: flex;
    gap: 8px;
    margin-top: 10px;
  }
</style>
