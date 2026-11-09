<script lang="ts">
  /**
   * QUI-P09 — the same narrow action, allowed again and again, offered as a rule.
   *
   * Following Muse's design write-up against approval fatigue: when the owner
   * keeps allowing one action to the same place, Raiker may *suggest* an
   * Allow-with-limits rule. It never creates one silently: nothing here is
   * kept until **Make this a rule** is pressed, and *Not now* hides that
   * suggestion in this browser only.
   */
  import { contract, type LimitRuleSuggestion } from "../generated/apiContract";
  import { humanize } from "../format";
  import { limitRuleReason } from "../limitRules";
  import { announcePermissionsChanged, onPermissionsChanged } from "../permissionSync";
  import { ApiError } from "../api";

  const DISMISSED = "raiker.limit-rule-suggestions.dismissed";

  let suggestions = $state<LimitRuleSuggestion[]>([]);
  let busy = $state<string | null>(null);
  let note = $state<string | null>(null);

  function keyOf(item: LimitRuleSuggestion): string {
    return `${item.tool_name}:${item.targets.join(",")}`;
  }

  function dismissed(): Set<string> {
    try {
      return new Set(JSON.parse(localStorage.getItem(DISMISSED) ?? "[]") as string[]);
    } catch {
      return new Set();
    }
  }

  async function load() {
    try {
      const hidden = dismissed();
      suggestions = (await contract.limitRuleSuggestions()).suggestions.filter((item) => !hidden.has(keyOf(item)));
    } catch {
      suggestions = [];
    }
  }

  $effect(() => {
    void load();
    return onPermissionsChanged(() => void load());
  });

  function notNow(item: LimitRuleSuggestion) {
    try {
      localStorage.setItem(DISMISSED, JSON.stringify([...dismissed(), keyOf(item)]));
    } catch {
      // Without storage it is hidden until the page is reloaded.
    }
    suggestions = suggestions.filter((other) => other !== item);
  }

  async function makeRule(item: LimitRuleSuggestion) {
    busy = keyOf(item);
    note = null;
    try {
      const made = await contract.createStandingGrant({
        action_type: item.tool_name,
        tool_name: item.tool_name,
        risk_ceiling: item.risk_level,
        reason: `Suggested after ${item.count} allows of the same action`,
        limits: item.limits as unknown as Record<string, unknown>,
      });
      note = `Rule kept. ${made.grant.limits_words.slice(0, 3).join(" · ")}.`;
      announcePermissionsChanged("rules");
      suggestions = suggestions.filter((other) => other !== item);
    } catch (error) {
      note = limitRuleReason(error instanceof ApiError ? error.reasonCode : null);
    } finally {
      busy = null;
    }
  }
</script>

{#if suggestions.length > 0 || note}
  <section class="suggestions" aria-label="Rules you could make">
    {#each suggestions as item (keyOf(item))}
      <div class="suggestion">
        <p>
          You allowed <strong>{humanize(item.tool_name)}</strong> to {item.targets.join(", ")}
          {item.count} times this week. Let it go ahead in conversations set to <strong>Within limits</strong>,
          up to {item.limits.max_uses} times for a week? Sensitive content and attachments would still ask.
        </p>
        <div class="actions">
          <button type="button" class="btn btn-sm" onclick={() => notNow(item)} disabled={busy !== null}>Not now</button>
          <button type="button" class="btn btn-primary btn-sm" onclick={() => void makeRule(item)} disabled={busy !== null}>
            {busy === keyOf(item) ? "Keeping…" : "Make this a rule"}
          </button>
        </div>
      </div>
    {/each}
    {#if note}<p class="note" role="status">{note}</p>{/if}
  </section>
{/if}

<style>
  .suggestions { display: grid; gap: 0.5rem; margin-bottom: var(--space-3); }
  .suggestion {
    display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.6rem;
    padding: 0.65rem 0.85rem; border: 1px solid var(--border); border-radius: var(--r-md); background: var(--surface);
  }
  .suggestion p { margin: 0; flex: 1 1 28rem; font-size: var(--text-sm); color: var(--text-1); }
  .actions { display: flex; gap: 0.5rem; }
  .note { margin: 0; font-size: var(--text-sm); color: var(--text-2); }
</style>
