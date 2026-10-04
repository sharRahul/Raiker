<script lang="ts">
  /**
   * UX-MODEL-01 — the model picker dialog, out of the Models page.
   *
   * Which of a provider's models stay offered, or — when the provider will not
   * list them — the one model id the owner types. The page owns reading the
   * catalogue and selecting; this draws the answer and says why a list is
   * missing in the provider's own terms.
   */
  import ProviderLogo from "../../components/ProviderLogo.svelte";
  import type { ModelProfile, ProviderModelList } from "../../apiTypes";
  import { providerName } from "../../format";
  import { providerErrorGuidance } from "../../providerErrors";
  import AvailableModels from "./AvailableModels.svelte";

  let {
    profile,
    list,
    loading,
    chosen,
    selecting,
    selectError,
    choice = $bindable(""),
    onclose,
    onuse,
    onsaved,
  }: {
    profile: ModelProfile;
    list: ProviderModelList | null;
    loading: boolean;
    /** The models currently kept offered for this profile. */
    chosen: string[];
    selecting: boolean;
    selectError: string | null;
    /** The typed model id, when the provider does not list its models. */
    choice?: string;
    onclose: () => void;
    onuse: (model: string) => void;
    onsaved: () => void;
  } = $props();

  function pickerNote(list: ProviderModelList): string {
    switch (list.status) {
      case "policy_denied":
        return "Model list denied by provider policy — enable the provider's gate first. You can still type a model id.";
      case "unsupported":
        return "This provider does not support model listing — type a model id.";
      default: {
        // The FIXED-355 / FIXED-370 defect, alive in the *other* control on
        // this page. `testNote` has read the server's classification since
        // BUG-272; this one printed "Provider unreachable" for every failure —
        // and it is the one on the path an owner actually walks, because
        // choosing a model is what you do straight after connecting.
        //
        // A live run against an identity-linked key showed it: the provider
        // answered in full, naming the workspace id it wanted, and the picker
        // said the provider could not be reached.
        const guidance = providerErrorGuidance(list.reason_code);
        if (guidance !== null) return `${guidance.message} ${guidance.fix}`;
        return "Provider unreachable — type a model id if you know it.";
      }
    }
  }
</script>

<div
  class="signin-overlay"
  role="presentation"
  onclick={(event) => event.target === event.currentTarget && onclose()}
>
  <div
    class="signin-dialog picker-dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="picker-title"
    tabindex="-1"
  >
    <button class="close" aria-label="Close model picker" onclick={onclose}>×</button>
    <div class="signin-logo">
      <ProviderLogo provider={profile.provider} size={40} />
    </div>
    <h2 id="picker-title">{providerName(profile.provider)} models</h2>
    {#if loading}
      <p class="picker-note" role="status">
        Loading models from {providerName(profile.provider)}…
      </p>
    {:else if list !== null && list.status === "available" && list.models.length > 0}
      <!-- Each switch is the whole decision: on means this model is offered
           everywhere, off means it is not. There is no second "Use model"
           step, because there was never a second question. -->
      <AvailableModels
        profileId={profile.profile_id}
        catalogue={list.models}
        {chosen}
        {onsaved}
      />
      <div class="picker-actions">
        <button type="button" class="btn btn-ghost btn-sm" onclick={onclose}>Done</button>
      </div>
    {:else}
      <p class="picker-note">
        {list !== null
          ? pickerNote(list)
          : "Model list unavailable — enter a custom model name."}
      </p>
      <input
        class="picker-input"
        type="text"
        placeholder="Custom model name"
        bind:value={choice}
        aria-label="Custom model name"
      />
      <div class="picker-actions">
        <button
          type="button"
          class="btn btn-primary btn-sm"
          onclick={() => onuse(choice)}
          disabled={selecting || choice.trim() === ""}
          >{selecting ? "Selecting…" : "Use model"}</button
        >
        <button type="button" class="btn btn-ghost btn-sm" onclick={onclose}>Cancel</button>
      </div>
      {#if selectError}<p class="error picker-error" role="alert">{selectError}</p>{/if}
    {/if}
  </div>
</div>

<style>
  /* The dialog frame it shares with the page's sign-in dialog. */
  .signin-overlay {
    align-items: center;
    background: var(--overlay);
    display: flex;
    inset: 0;
    justify-content: center;
    padding: var(--space-4);
    position: fixed;
    z-index: var(--z-scrim);
  }
  .signin-dialog {
    position: relative;
    width: min(100%, 26rem);
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-top: 4px solid var(--brand);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-2);
    padding: 1.6rem 1.5rem 1.3rem;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }
  .signin-dialog .close {
    position: absolute;
    top: 0.6rem;
    right: 0.7rem;
    background: transparent;
    border: 0;
    color: var(--text-2);
    cursor: pointer;
    font-size: var(--text-2xl);
    line-height: 1;
  }
  .signin-logo {
    min-height: 3rem;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 0.1rem;
  }
  .signin-dialog h2 {
    margin: 0;
    text-align: center;
    font-size: var(--text-xl);
  }
  .picker-dialog {
    display: grid;
    gap: 0.7rem;
    text-align: left;
  }
  .picker-dialog h2 {
    margin: 0;
  }
  .picker-input {
    padding: 0.35rem 0.5rem;
    border-radius: var(--r-md);
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: var(--text-1);
    max-width: 100%;
    font: inherit;
    font-size: var(--text-md);
  }
  .picker-note {
    font-size: var(--text-xs);
    color: var(--text-3);
    margin: 0;
  }
  .picker-actions {
    display: flex;
    gap: 0.4rem;
  }
  .picker-error {
    font-size: var(--text-sm);
    margin: 0;
  }
</style>
