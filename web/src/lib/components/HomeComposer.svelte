<script lang="ts">
  /**
   * QUI-H01 — Home opens with a composer, so landing on Home feels like
   * landing in Chat.
   *
   * It does not send anything itself. The message is handed to Chat
   * (`chatHandoff.ts`), which starts a new conversation and sends it through
   * the one governed send path; Home then opens Chat to show it.
   *
   * QUI-H02 — on a first day, with nothing in the workspace yet, the four
   * starters sit under it. A question starter fills the box for the owner to
   * edit; a place starter opens Build or Design.
   */
  import Icon from "./Icon.svelte";
  import { handOffToChat } from "../chatHandoff";
  import { STARTERS } from "../starters";

  let { showStarters = false }: { showStarters?: boolean } = $props();

  let text = $state("");
  let input = $state<HTMLTextAreaElement>();

  function send(event?: Event) {
    event?.preventDefault();
    if (text.trim() === "") return;
    handOffToChat(text);
    text = "";
    window.location.hash = "#/new-chat";
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) send(event);
  }

  function useStarter(prompt: string) {
    text = prompt;
    input?.focus();
  }
</script>

<form class="home-composer" onsubmit={send}>
  <label class="sr-only" for="home-prompt">Ask Raiker</label>
  <textarea
    id="home-prompt"
    bind:this={input}
    bind:value={text}
    rows="2"
    placeholder="Ask Raiker anything…"
    title="Enter to send, Shift+Enter for a new line"
    onkeydown={onKeydown}
  ></textarea>
  <div class="home-composer-row">
    <span class="hint">Opens a new chat</span>
    <button type="submit" class="btn btn-primary btn-sm send" disabled={text.trim() === ""} aria-label="Send">
      <Icon name="send" size="sm" />
    </button>
  </div>
</form>

{#if showStarters}
  <ul class="starters" aria-label="Ways to start">
    {#each STARTERS as starter (starter.id)}
      <li>
        {#if starter.kind === "prompt"}
          <button type="button" class="starter" onclick={() => useStarter(starter.prompt)}>
            <Icon name={starter.icon} size="sm" /><span>{starter.label}</span>
          </button>
        {:else}
          <a class="starter" href={starter.href}>
            <Icon name={starter.icon} size="sm" /><span>{starter.label}</span>
          </a>
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<style>
  .home-composer {
    display: grid;
    gap: var(--space-2);
    max-width: 46rem;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
  }
  .home-composer:focus-within { border-color: var(--accent-border); }
  textarea {
    width: 100%;
    min-height: 3.5rem;
    max-height: 11rem;
    resize: vertical;
    border: 0;
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: var(--text-base);
    line-height: 1.5;
  }
  textarea:focus { outline: none; }
  .home-composer-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
  .hint { font-size: var(--text-xs); color: var(--text-3); }
  .send { width: 2.5rem; height: 2.5rem; padding: 0; display: inline-grid; place-items: center; border-radius: var(--r-md); }
  .starters {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
    gap: var(--space-2);
    max-width: 46rem;
  }
  .starter {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--surface);
    color: var(--text-1);
    font: inherit;
    font-size: var(--text-sm);
    text-align: left;
    text-decoration: none;
    cursor: pointer;
  }
  .starter:hover { border-color: var(--accent-border); }
</style>
