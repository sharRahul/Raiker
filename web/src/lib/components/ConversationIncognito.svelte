<script lang="ts">
  import { api } from "../api";

  let {
    sessionId = $bindable<string | null>(null),
    incognito = $bindable(false),
    busy = $bindable(false),
    disabled = false,
    onsaved = () => {},
  } = $props<{
    sessionId?: string | null; incognito?: boolean; busy?: boolean; disabled?: boolean;
    onsaved?: (id: string) => void;
  }>();
  let error = $state("");

  async function toggle() {
    if (busy || disabled) return;
    busy = true;
    error = "";
    try {
      const result = sessionId === null
        ? await api.startIncognitoConversation()
        : await api.setSessionIncognito(sessionId, !incognito);
      incognito = result.incognito;
      sessionId = result.session_id;
      onsaved(result.session_id);
    } catch {
      error = "Could not change Incognito. Try again.";
    } finally {
      busy = false;
    }
  }
</script>

<div class="conversation-incognito">
  <button type="button" class="btn btn-ghost btn-sm" role="switch"
    aria-label="Incognito for this conversation" aria-checked={incognito}
    disabled={disabled || busy} onclick={() => void toggle()}>
    Incognito · {busy ? "Saving…" : incognito ? "On" : "Off"}
  </button>
  {#if incognito}<p class="hint">No recalled memories or earlier chats. Messages in this chat are still saved.</p>{/if}
  {#if error}<p role="alert">{error}</p>{/if}
</div>

<style>
  .conversation-incognito { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); }
  p { margin: 0; font-size: var(--text-sm); color: var(--text-muted); }
  .hint { max-width: 28rem; }
</style>
