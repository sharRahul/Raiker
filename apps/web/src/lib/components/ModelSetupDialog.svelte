<script lang="ts">
  import type { ModelReadinessView } from "../apiTypes";
  import {
    closeModelSetup,
    refreshModelReadiness,
    setupDialog,
  } from "../modelReadiness.svelte";

  let {
    readiness = null,
    draftPreserved = false,
    onRetry,
  }: {
    readiness?: ModelReadinessView | null;
    draftPreserved?: boolean;
    onRetry?: () => Promise<unknown> | unknown;
  } = $props();

  let dialog: HTMLDialogElement | undefined = $state();
  let checking = $state(false);
  let retryStatus = $state("");
  const activeReadiness = $derived(readiness ?? setupDialog.readiness);
  const visible = $derived(readiness !== null || setupDialog.open);
  const isSetup = $derived(
    activeReadiness === null ||
      activeReadiness.state === "not_configured" ||
      activeReadiness.state === "model_missing" ||
      activeReadiness.state === "runtime_missing",
  );
  // A check that succeeded is not a repair. The dialog had two titles for three
  // outcomes, so re-checking a model that turned out to be fine kept a heading
  // that said something was wrong with it — while the line underneath said the
  // provider could reach it. Naming the third outcome is what makes the two
  // halves of the dialog agree.
  const isReady = $derived(activeReadiness?.state === "ready");
  const title = $derived(
    isReady
      ? "This model is ready"
      : isSetup
        ? "Set up a model to continue"
        : "Repair model connection",
  );

  $effect(() => {
    if (!dialog) return;
    if (visible && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    } else if (!visible && dialog.open) {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }
  });

  function close() {
    if (readiness !== null) {
      dialog?.removeAttribute("open");
    }
    closeModelSetup();
  }

  function openModels() {
    window.location.hash = "#/models";
    close();
  }

  async function retry() {
    checking = true;
    retryStatus = "Checking model reachability…";
    try {
      const result = await (onRetry ? onRetry() : refreshModelReadiness());
      // `refreshModelReadiness` returns null when there is no profile *and* no
      // model to check — which is the state this dialog is most often opened in.
      // It used to report "Check complete" anyway, so the one control on the
      // screen claimed to have proven a model it had never contacted. Saying what
      // actually happened is the difference between a check and a placebo.
      retryStatus =
        result === null && !onRetry
          ? "There is no model to check yet. Choose one in Models first."
          : "Check complete";
    } catch {
      retryStatus = "Check failed. Open Models to review the connection.";
    } finally {
      checking = false;
    }
  }

  function trapFocus(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab" || !dialog) return;
    const items = [...dialog.querySelectorAll<HTMLElement>(
      'button:not([disabled]), summary, a[href], [tabindex]:not([tabindex="-1"])',
    )];
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
</script>

{#if visible}
  <dialog bind:this={dialog} aria-labelledby="model-setup-title" onkeydown={trapFocus} oncancel={(event) => { event.preventDefault(); close(); }}>
    <div class="dialog-card">
      <div class="eyebrow">Model readiness</div>
      <h2 id="model-setup-title">{title}</h2>
      <p class="summary">{activeReadiness?.summary ?? "No model is set up for this action."}</p>
      <p>{activeReadiness?.remediation ?? "Open Models to connect a provider or install a local runtime and model."}</p>
      {#if draftPreserved}<p class="preserved">Your draft is preserved.</p>{/if}

      {#if activeReadiness}
        <details>
          <summary>Technical details</summary>
          <dl>
            <dt>Reason</dt><dd><code>{activeReadiness.reason_code}</code></dd>
            <dt>Profile</dt><dd><code>{activeReadiness.profile_id}</code></dd>
            <dt>Model</dt><dd><code>{activeReadiness.model}</code></dd>
          </dl>
        </details>
      {/if}

      {#if retryStatus}<p class="retry-status" role="status">{retryStatus}</p>{/if}
      <div class="actions">
        <!-- Once the model is ready, the thing to do is carry on with what the
             dialog interrupted. Leaving "Open Models" as the primary action sent
             the owner to a page with nothing left to fix on it. -->
        {#if isReady}
          <button class="secondary" type="button" onclick={openModels}>Open Models</button>
          <button class="primary" type="button" onclick={close}>Continue</button>
        {:else}
          <button class="secondary" type="button" onclick={close}>Close</button>
          {#if activeReadiness}
            <button class="secondary" type="button" disabled={checking} onclick={retry}>Check again</button>
          {/if}
          <button class="primary" type="button" onclick={openModels}>Open Models</button>
        {/if}
      </div>
    </div>
  </dialog>
{/if}

<style>
  dialog { width: min(31rem, calc(100vw - 2rem)); padding: 0; border: 1px solid var(--neutral-border); border-radius: var(--r-lg); background: var(--surface); color: var(--text-2); box-shadow: var(--shadow-2); }
  dialog::backdrop { background: var(--overlay); backdrop-filter: blur(3px); }
  .dialog-card { padding: 1.2rem; }
  .eyebrow { color: var(--accent); font-size: .68rem; font-weight: 800; letter-spacing: .09em; text-transform: uppercase; }
  h2 { margin: .3rem 0 .6rem; color: var(--text-1); font-size: 1.2rem; }
  p { margin: .35rem 0; font-size: .82rem; line-height: 1.5; }
  .summary { color: var(--text-1); font-weight: 700; }
  .preserved { color: var(--text-3); }
  details { margin-top: .85rem; border-top: 1px solid var(--border); padding-top: .65rem; font-size: var(--text-sm); }
  summary { width: max-content; color: var(--text-2); cursor: pointer; }
  dl { display: grid; grid-template-columns: auto 1fr; gap: .35rem .65rem; }
  dt { color: var(--text-3); } dd { margin: 0; overflow-wrap: anywhere; }
  .retry-status { color: var(--text-3); }
  .actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: .45rem; margin-top: 1rem; }
  button { border-radius: var(--r-pill); padding: .42rem .72rem; font: inherit; font-size: var(--text-sm); font-weight: 750; cursor: pointer; }
  button:disabled { opacity: .62; cursor: wait; }
  .secondary { border: 1px solid var(--neutral-border); background: var(--surface); color: var(--text-1); }
  .primary { border: 1px solid var(--accent-border); background: var(--accent); color: var(--accent-contrast, white); }
</style>
