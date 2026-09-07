<script lang="ts">
  /**
   * Privacy — what Raiker keeps of a turn beyond its answer (BUG-215).
   *
   * The reasoning question is the reason this section exists. A turn with
   * Thinking on streams the model's own working into a collapsed block; that
   * working can restate anything the prompt contained, and it is the one part of
   * a turn an owner may specifically not want on disk. So it is **not** kept
   * unless the owner says so here — and, when it is not kept, the transcript
   * says that rather than showing nothing and implying the turn never thought.
   */
  let { settings, save }: {
    settings: Record<string, unknown>;
    save: (p: Record<string, unknown>) => void;
  } = $props();

  const retainReasoning = $derived(settings["privacy.retain_reasoning"] === true);
</script>

<header class="section-heading">
  <h2>Privacy</h2>
  <p>Choose what Raiker keeps of a turn once the turn is over.</p>
</header>

<section class="settings-card" aria-labelledby="retained-working">
  <div class="card-heading">
    <h3 id="retained-working">Retained working</h3>
    <p>
      With Thinking on, Raiker shows the model's own working above its answer while
      the turn runs. This decides whether that working is written to the encrypted
      store so a re-opened conversation still shows it.
    </p>
  </div>

  <label class="toggle">
    <input
      type="checkbox"
      checked={retainReasoning}
      onchange={(e) => save({ "privacy.retain_reasoning": e.currentTarget.checked })}
    />
    <span>
      <strong>Keep the model's working with the turn</strong>
      <small>
        Off by default. The working can restate anything your prompt contained, so
        it is kept only if you ask. It is stored under the same encryption as the
        rest of the conversation, is never added to chat search, and is never
        included in an exported transcript.
      </small>
    </span>
  </label>

  <p class="note">
    Turning this off does not erase working already kept, and it does not hide that
    there was any: a turn whose working was not kept says so in the transcript,
    rather than reading as a turn that never thought.
  </p>
</section>

<style>
  .section-heading { margin-bottom: var(--space-4); }
  .section-heading h2, .card-heading h3 { margin: 0; }
  .section-heading p, .card-heading p { color: var(--text-2); margin: .3rem 0 0; }
  .settings-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: var(--card-pad-y) var(--card-pad-x);
    margin-bottom: var(--space-4);
  }
  .toggle {
    display: flex;
    align-items: flex-start;
    gap: .6rem;
    max-width: 40rem;
    margin-top: var(--space-5);
  }
  .toggle span { display: grid; gap: .2rem; }
  .toggle small { color: var(--text-2); line-height: 1.5; }
  .note {
    max-width: 40rem;
    margin: var(--space-4) 0 0;
    color: var(--text-3);
    font-size: var(--text-sm);
    line-height: 1.55;
  }
</style>
