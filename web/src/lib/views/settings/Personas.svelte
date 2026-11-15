<script lang="ts">
  /**
   * ADR-0005 — the owner's personas: `@DataAnalyst` in the composer.
   *
   * A list of rows (name, what it does, Edit) with **Add persona**; each opens
   * a form dialog (QUI-L03). A persona is instructions, an optional default
   * model and an optional set of tool families. It can only narrow a turn:
   * the families it leaves out are withheld from the turn and denied, and
   * nothing here can give a turn more than Permissions already does.
   */
  import FormDialog from "../../components/FormDialog.svelte";
  import { ApiError, api } from "../../api";
  import { failure } from "../../errorCopy";
  import type { PersonaFamily, PersonaRequest, PersonaView } from "../../generated/apiContract";

  const MAX_INSTRUCTIONS = 4000;
  const REASONS: Record<string, string> = {
    invalid_persona_name: "A name is letters and digits, starting with a letter (for example DataAnalyst).",
    persona_name_taken: "You already have a persona with that name.",
    persona_instructions_required: "Write what the persona should do.",
    persona_instructions_too_long: `Instructions can be at most ${MAX_INSTRUCTIONS.toLocaleString()} characters.`,
    persona_model_needs_profile: "Choose the connection the model belongs to.",
    too_many_personas: "You have the most personas one account can keep. Remove one first.",
  };

  let personas = $state<PersonaView[]>([]);
  let families = $state<PersonaFamily[]>([]);
  let loadError = $state<string | null>(null);
  let loaded = $state(false);

  // The dialog: `null` is closed; `"new"` adds; an id edits that persona.
  let editing = $state<string | null>(null);
  let name = $state("");
  let description = $state("");
  let instructions = $state("");
  let limitTools = $state(false);
  let kept = $state<string[]>([]);
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let confirmingRemove = $state(false);

  async function load() {
    loadError = null;
    try {
      const view = await api.personas();
      personas = view.personas;
      families = view.families;
    } catch (e) {
      loadError = failure("Your personas could not be read", "The @ menu offers files only until they are.", "Choose Retry to read them again.", e);
    } finally {
      loaded = true;
    }
  }

  function open(persona: PersonaView | null) {
    editing = persona?.persona_id ?? "new";
    name = persona?.name ?? "";
    description = persona?.description ?? "";
    instructions = persona?.instructions ?? "";
    limitTools = persona?.tool_ceiling != null;
    kept = persona?.tool_ceiling ?? families.map((family) => family.family);
    formError = null;
    confirmingRemove = false;
  }

  function toolSummary(persona: PersonaView): string {
    if (persona.tool_ceiling === null) return "Every tool the turn has";
    if (persona.tool_ceiling.length === 0) return "No tools";
    const labels = families.filter((family) => persona.tool_ceiling?.includes(family.family)).map((family) => family.label);
    return labels.join(", ");
  }

  async function save() {
    if (editing === null) return;
    saving = true;
    formError = null;
    const current = personas.find((persona) => persona.persona_id === editing);
    const body: PersonaRequest = {
      name: name.trim().replace(/^@/, ""),
      description: description.trim(),
      instructions,
      model_profile: current?.model_profile ?? null,
      model: current?.model ?? null,
      tool_ceiling: limitTools ? families.map((family) => family.family).filter((family) => kept.includes(family)) : null,
    };
    try {
      if (editing === "new") await api.createPersona(body);
      else await api.updatePersona(editing, body);
      editing = null;
      await load();
    } catch (e) {
      const code = e instanceof ApiError ? (e.reasonCode ?? "") : "";
      formError = REASONS[code] ?? failure("The persona was not saved", "Nothing was changed.", "Choose Save to try again.", e);
    } finally {
      saving = false;
    }
  }

  async function remove() {
    if (editing === null || editing === "new") return;
    saving = true;
    formError = null;
    try {
      await api.deletePersona(editing);
      editing = null;
      await load();
    } catch (e) {
      formError = failure("The persona was not removed", "It is still in the @ menu.", "Choose Remove to try again.", e);
    } finally {
      saving = false;
    }
  }

  void load();
</script>

<section class="settings-card" aria-labelledby="personas-h" data-testid="personas">
  <div class="card-heading">
    <h3 id="personas-h">Personas</h3>
    <p>Type <kbd>@</kbd> in Chat to answer as one. A persona changes how Raiker answers, never what it is allowed to do.</p>
  </div>
  {#if loadError}
    <p class="error" role="alert">{loadError}</p>
    <button type="button" class="btn btn-sm" onclick={() => void load()}>Retry</button>
  {:else if loaded}
    {#if personas.length === 0}
      <p class="empty">No personas yet. Add one for work you ask for often, such as a data analyst or a copywriter.</p>
    {:else}
      <ul class="persona-list" aria-label="Your personas">
        {#each personas as persona (persona.persona_id)}
          <li class="persona-row">
            <span class="persona-name">@{persona.name}</span>
            <span class="persona-detail">
              {#if persona.description}<span>{persona.description}</span>{/if}
              <span class="persona-tools">{toolSummary(persona)}</span>
            </span>
            <button type="button" class="btn btn-sm" aria-label={`Edit @${persona.name}`} onclick={() => open(persona)}>Edit</button>
          </li>
        {/each}
      </ul>
    {/if}
    <div class="actions">
      <button type="button" class="btn btn-sm" onclick={() => open(null)}>Add persona</button>
    </div>
  {:else}
    <p class="empty">Reading…</p>
  {/if}
</section>

{#if editing !== null}
  <FormDialog title={editing === "new" ? "Add persona" : `Edit @${name || "persona"}`} onclose={() => { if (!saving) editing = null; }}>
    <label>
      Name
      <input class="settings-input" bind:value={name} placeholder="DataAnalyst" autocomplete="off" spellcheck="false" />
      <small>What you type after @. Letters and digits.</small>
    </label>
    <label>
      Description <span class="optional">(optional)</span>
      <input class="settings-input" bind:value={description} maxlength="200" placeholder="Reads numbers carefully" />
    </label>
    <label>
      Instructions
      <textarea class="settings-input instructions" bind:value={instructions} rows="6" maxlength={MAX_INSTRUCTIONS}
        placeholder="Lead with the figures, then explain them in one sentence."></textarea>
      <small>{instructions.length.toLocaleString()} of {MAX_INSTRUCTIONS.toLocaleString()} characters. Raiker's own rules still apply.</small>
    </label>
    <fieldset class="tools">
      <legend>Tools</legend>
      <label class="check">
        <input type="checkbox" bind:checked={limitTools} />
        Only some tools
      </label>
      {#if limitTools}
        <div class="families">
          {#each families as family (family.family)}
            <label class="check">
              <input type="checkbox" value={family.family} bind:group={kept} />
              {family.label}
            </label>
          {/each}
        </div>
        <small>Tools left out are not offered to the turn and are refused if asked for.</small>
      {:else}
        <small>Uses every tool the turn already has. It never gets more.</small>
      {/if}
    </fieldset>
    {#if formError}<p class="error" role="alert">{formError}</p>{/if}
    <div class="dialog-actions">
      {#if editing !== "new"}
        {#if confirmingRemove}
          <button type="button" class="btn btn-sm btn-danger" disabled={saving} onclick={() => void remove()}>Remove @{name}</button>
          <button type="button" class="btn btn-ghost btn-sm" disabled={saving} onclick={() => (confirmingRemove = false)}>Keep</button>
        {:else}
          <button type="button" class="btn btn-ghost btn-sm" disabled={saving} onclick={() => (confirmingRemove = true)}>Remove…</button>
        {/if}
      {/if}
      <span class="spacer"></span>
      <button type="button" class="btn btn-ghost btn-sm" disabled={saving} onclick={() => (editing = null)}>Cancel</button>
      <button type="button" class="btn btn-primary btn-sm" disabled={saving || !name.trim() || !instructions.trim()} onclick={() => void save()}>
        {saving ? "Saving…" : "Save"}
      </button>
    </div>
  </FormDialog>
{/if}

<style>
  .card-heading h3 { margin: 0; }
  .card-heading p { color: var(--text-2); margin: 0.3rem 0 0; }
  .empty { color: var(--text-2); font-size: var(--text-sm); margin: var(--space-3) 0 0; }
  .persona-list { list-style: none; margin: var(--space-3) 0 0; padding: 0; }
  .persona-row {
    display: grid;
    grid-template-columns: minmax(8rem, 0.8fr) minmax(0, 2fr) auto;
    align-items: center;
    gap: var(--space-3);
    min-height: 52px;
    border-top: 1px solid var(--border);
  }
  .persona-row:first-child { border-top: none; }
  .persona-name { font-weight: 650; font-size: var(--text-sm); overflow-wrap: anywhere; }
  .persona-detail { display: grid; gap: 0.1rem; color: var(--text-2); font-size: var(--text-sm); min-width: 0; }
  .persona-detail > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .persona-tools { color: var(--text-3); font-size: var(--text-xs); }
  .actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
  label { display: grid; gap: 0.3rem; margin-top: var(--space-4); font-weight: 650; }
  label:first-child { margin-top: 0; }
  label small, .tools small { color: var(--text-2); font-weight: 400; font-size: var(--text-xs); }
  .optional { color: var(--text-3); font-weight: 400; }
  .settings-input {
    width: 100%; min-height: 44px; padding: 0 0.8rem;
    border: 1px solid var(--border-strong); border-radius: var(--r-md);
    background: var(--surface); color: var(--text-1); font: inherit; box-sizing: border-box;
  }
  .settings-input.instructions { padding: 0.6rem 0.8rem; min-height: 8rem; resize: vertical; line-height: 1.5; }
  .settings-input:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 2px; }
  .tools { border: 0; padding: 0; margin: var(--space-4) 0 0; display: grid; gap: var(--space-2); }
  .tools legend { font-weight: 650; padding: 0; margin-bottom: var(--space-1); }
  .check { display: flex; align-items: center; gap: var(--space-2); margin: 0; font-weight: 400; }
  .families { display: grid; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); gap: var(--space-2); padding-left: var(--space-5); }
  .dialog-actions { display: flex; align-items: center; gap: var(--space-2); margin-top: var(--space-5); flex-wrap: wrap; }
  .spacer { flex: 1; }
  .error { color: var(--danger); font-size: var(--text-sm); margin: var(--space-3) 0 0; }
  kbd { font: inherit; font-size: var(--text-xs); padding: 0 0.3rem; border: 1px solid var(--border); border-radius: var(--r-sm); }
</style>
