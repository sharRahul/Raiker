<script lang="ts">
  import { api } from "../../api";
  import { inDesktopShell } from "../../desktopShell";
  import { DISPLAY_LOCALES } from "../../format";
  import {
    TIMEZONE_KEY,
    localTimeIn,
    utcOffset,
    resolvedTimezone,
    timezoneOptions,
    timezoneProposal,
    timezoneSourceLabel,
  } from "../../environment";

  /*
   * REM-SET-GENERAL — General says what it decides, once.
   *
   * The page carried three cards of setup teaching: a paragraph on the header, a
   * paragraph on each card heading, and a sentence under most controls, several
   * of them restating each other. An owner reading a settings page is looking
   * for the control, and prose between them is what made a short page long.
   *
   * What is kept is the distinction that actually changes the answer, and it is
   * now said in one line per card rather than three: **language and region are
   * interface formatting; the time zone is what every model turn is told.**
   * Those are different kinds of setting that happened to sit under one word,
   * and confusing them is how somebody sets a region to fix a schedule.
   *
   * The default weather location moved to Personalisation, where the review put
   * it. It is optional, it is a preference about answers rather than about the
   * runtime, and it was the only control on this page that was neither.
   *
   * DEC-21 General — three languages, each doing the one thing it says. The
   * card promised "interface text and formatting" and did neither: the
   * interface is written in English, nothing read the Language value, and a
   * Country or region select changed nothing at all. Now:
   *
   * - **Dates and times** sets the format every date and time is written in;
   * - **Speech** is dictation and read-aloud, as before;
   * - **Answers** is what models are told about the language to answer in —
   *   the one of the three that reaches a model, said so on the control.
   *
   * The region select is gone rather than relabelled: it had no effect to
   * describe. Its stored value stays readable and untouched.
   */

  let { settings, save }: {
    settings: Record<string, unknown>;
    save: (p: Record<string, unknown>) => void;
  } = $props();

  const language = $derived((settings["general.language"] as string) ?? "");
  const answerLanguage = $derived((settings["general.answer_language"] as string) ?? "");
  const startupRoute = $derived((settings["general.startup_route"] as string) ?? "workbench");
  /**
   * QUI-A rules — how much of an answer Raiker draws. The runtime reads this
   * for every turn; a stored value this build does not offer reads as Auto,
   * which is also what the runtime does with it.
   */
  const answerStyle = $derived(
    ["auto", "text", "visual"].includes(settings["chat.answer_style"] as string)
      ? (settings["chat.answer_style"] as string)
      : "auto",
  );

  // QUI-W06 — reopen first-run setup on its model step.
  let setupBusy = $state(false);
  let setupError = $state<string | null>(null);
  async function runSetupAgain() {
    setupBusy = true;
    setupError = null;
    try {
      // The update carries the whole stored state, so every earlier choice is
      // kept; only where setup stands changes.
      const stored = await api.setup();
      await api.updateSetup({
        status: "in_progress",
        stage: "model",
        selected_profile_id: stored.selected_profile_id,
        selected_model: stored.selected_model,
        model_deferred: stored.model_deferred,
        privacy_mode: stored.privacy_mode,
        backup_mode: stored.backup_mode,
        backup_target: stored.backup_target,
        background_service_enabled: stored.background_service_enabled,
      });
      window.location.hash = "#/model-setup";
    } catch {
      setupError = "Setup could not be reopened. Nothing was changed.";
    } finally {
      setupBusy = false;
    }
  }

  // The time zone is not a formatting preference here. It is the one
  // owner-level value every model turn reasons from, so the control shows what
  // is actually in force, where that came from, and what the owner's clock reads
  // in it right now. A select whose effect you cannot see is a select nobody
  // trusts.
  const zones = timezoneOptions();
  const resolved = $derived(resolvedTimezone(settings));
  const explicit = $derived((settings[TIMEZONE_KEY] as string) ?? "");
  // BUG-321 — a zone saved under its old name (Asia/Calcutta) is still the
  // owner's choice and still shown as chosen; the list itself offers the
  // current names.
  const zoneChoices = $derived(explicit && !zones.includes(explicit) ? [explicit, ...zones] : zones);
  // A device zone is *offered*, never applied. Somebody who set Europe/London
  // and opened Raiker from a hotel in Denver has said something about their
  // schedule; rewriting it silently would move every recurring task to fix a
  // problem they do not have.
  const proposal = $derived(timezoneProposal(settings));

  // Ticks so the sample clock stays true while the page is open. A frozen
  // timestamp under a control that claims to set the clock is worse than none.
  let now = $state(new Date());
  $effect(() => {
    const timer = setInterval(() => (now = new Date()), 30_000);
    return () => clearInterval(timer);
  });
  const sample = $derived(localTimeIn(resolved.zone, now));
  // The chosen date format, shown on its own control so its effect is visible
  // before anything else on the page re-renders.
  const formatSample = $derived(
    now.toLocaleString(language || undefined, { dateStyle: "medium", timeStyle: "short" }),
  );
  /** Kept in step with `raiker.runtime.environment.ANSWER_LANGUAGES`. */
  const ANSWER_LANGUAGES: { value: string; label: string }[] = [
    { value: "en", label: "English" },
    { value: "hi", label: "हिन्दी (Hindi)" },
    { value: "es", label: "Español (Spanish)" },
    { value: "fr", label: "Français (French)" },
    { value: "de", label: "Deutsch (German)" },
    { value: "it", label: "Italiano (Italian)" },
    { value: "pt", label: "Português (Portuguese)" },
    { value: "ja", label: "日本語 (Japanese)" },
  ];
  const offset = $derived(utcOffset(resolved.zone, now));
</script>

<header class="section-heading">
  <h2>General</h2>
</header>

<section class="settings-card" aria-labelledby="language-region">
  <div class="card-heading">
    <h3 id="language-region">Language and time</h3>
  </div>
  <label>
    <span>Dates and times</span>
    <small>Raiker's own text is in English. Right now: {formatSample}.</small>
    <select aria-label="Dates and times" value={language} onchange={(e) => save({ "general.language": e.currentTarget.value })}>
      <option value="">This browser's format</option>
      {#each DISPLAY_LOCALES as option (option.value)}
        <option value={option.value}>{option.label}</option>
      {/each}
    </select>
  </label>
  <label>
    <span>Time zone</span>
    <small>Turns, schedules and words like “tomorrow” use this zone.</small>
    <select
      aria-label="Time zone"
      value={explicit}
      onchange={(e) => save({ [TIMEZONE_KEY]: e.currentTarget.value })}
    >
      <option value="">Not set — Raiker falls back to UTC</option>
      {#each zoneChoices as zone (zone)}
        <option value={zone}>{zone}</option>
      {/each}
    </select>
  </label>
  <!-- The zone in force, its clock and its offset on one line; where the
       zone came from is the option the select already shows, so it is a title
       rather than a second sentence. -->
  <p class="resolved" data-testid="timezone-resolved" title={timezoneSourceLabel(resolved.source)}>
    <strong>{resolved.zone}</strong>
    {#if sample} · <span class="clock">{sample}</span>{/if}
    <!-- DEC-21 — the offset a schedule is computed from, said as a number. A
         task stores the zone it was composed in (UX-TASK-02), so changing this
         does not move a task that is already scheduled. -->
    {#if offset} · <span class="clock" data-testid="timezone-offset">{offset}; scheduled tasks keep their zone</span>{/if}
  </p>
  {#if proposal}
    <p class="proposal" data-testid="timezone-proposal">
      This device reports <strong>{proposal}</strong>. Raiker will not change your
      choice on its own.
      <button type="button" class="link" onclick={() => save({ [TIMEZONE_KEY]: proposal })}>
        Use {proposal}
      </button>
    </p>
  {/if}
  <label>
    <span>Answer in</span>
    <small>Every turn is told this; a message can still ask for another.</small>
    <select aria-label="Answer in" value={answerLanguage} onchange={(e) => save({ "general.answer_language": e.currentTarget.value })}>
      <option value="">The language of my message</option>
      {#each ANSWER_LANGUAGES as option (option.value)}
        <option value={option.value}>{option.label}</option>
      {/each}
    </select>
  </label>
</section>


<section class="settings-card" aria-labelledby="startup-behaviour">
  <div class="card-heading">
    <h3 id="startup-behaviour">Startup and answers</h3>
  </div>
  <label>
    <span>Default startup view</span>
    <small>The first page Raiker opens; links are unaffected.</small>
    <select value={startupRoute} onchange={(e) => save({ "general.startup_route": e.currentTarget.value })}>
      <option value="workbench">Home</option>
      <option value="new-chat">New chat</option>
      <option value="tasks">Tasks</option>
      <option value="projects">Projects</option>
      <option value="approvals">Approvals</option>
      <option value="last-visited">Last visited page</option>
    </select>
  </label>
  <!-- QUI-L09 — answer style sits with startup: the two ways Raiker
       behaves before you ask anything else of it, rather than a card of its own. -->
  <label id="answer-style">
    <span>Answer style</span>
    <small>How often answers use figures and charts instead of prose.</small>
    <select
      aria-label="Answer style"
      value={answerStyle}
      onchange={(e) => save({ "chat.answer_style": e.currentTarget.value })}
    >
      <option value="auto">Auto</option>
      <option value="text">Mostly text</option>
      <option value="visual">Visual where it helps</option>
    </select>
  </label>
  <!-- QUI-W06 — setup can be run again. It reopens the same focused setup on
       its model step; nothing already chosen is reset until the owner changes
       it there. -->
  <div class="setup-row">
    <div>
      <span id="setup-again" class="row-label">Setup</span>
      <small>Choose a model and where your data may go again.</small>
    </div>
    <div class="setup-again-row">
      <button type="button" class="btn btn-soft btn-sm" onclick={runSetupAgain} disabled={setupBusy}>
        {setupBusy ? "Opening…" : "Run setup again"}
      </button>
      {#if setupError}<span class="setup-error" role="alert">{setupError}</span>{/if}
    </div>
  </div>
</section>

{#if inDesktopShell()}
  <!-- QUI-F11 — the desktop window only: closing it can keep Raiker in the
       tray, where a dot shows while a decision waits. -->
  <section class="settings-card" aria-labelledby="desktop-window">
    <div class="card-heading">
      <h3 id="desktop-window">Desktop window</h3>
      <p>Raiker keeps working while its window is hidden; approvals still wait for you.</p>
    </div>
    <label class="tray-toggle">
      <input
        type="checkbox"
        checked={settings["desktop.minimize_to_tray"] === true}
        onchange={(e) => save({ "desktop.minimize_to_tray": e.currentTarget.checked })}
      />
      <span>Keep Raiker in the tray when you close its window</span>
    </label>
  </section>
{/if}


<style>
  .section-heading { margin-bottom: var(--space-3); }
  .tray-toggle { display: flex; align-items: center; gap: var(--space-2); flex-direction: row; }
  .section-heading h2, .card-heading h3 { margin: 0; }
  .card-heading p { color: var(--text-2); margin: .3rem 0 0; }
  .settings-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: var(--card-pad-y) var(--card-pad-x); margin-bottom: var(--space-4); }
  /* QUI-L03 — a setting is a row: its name and help on the left, the control
     on the right, so a card of three choices is three rows rather than three
     stacked forms. */
  label {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(14rem, 20rem);
    column-gap: var(--space-4);
    row-gap: .15rem;
    align-items: center;
    margin-top: var(--space-2);
    font-weight: 650;
  }
  label > span, label > small { grid-column: 1; }
  label > select { grid-column: 2; grid-row: 1 / span 2; }
  label small { color: var(--text-2); font-weight: 400; font-size: var(--text-sm); }
  select { width: 100%; }
  .settings-card { padding: var(--space-3) var(--card-pad-x) var(--space-4); margin-bottom: var(--space-3); }
  .card-heading p { font-size: var(--text-sm); }
  .resolved { color: var(--text-2); margin: var(--space-2) 0 0; font-size: var(--text-sm); }
  .resolved strong { color: var(--text-1); }
  .clock { font-variant-numeric: tabular-nums; }
  .proposal { color: var(--text-2); margin: var(--space-2) 0 0; max-width: 34rem; }
  .proposal strong { color: var(--text-1); }
  .setup-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); margin-top: var(--space-2); }
  .setup-row > div:first-child { display: grid; gap: .15rem; }
  .row-label { font-weight: 650; }
  .setup-row small { color: var(--text-2); font-size: var(--text-sm); }
  .setup-again-row { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
  .setup-error { font-size: var(--text-sm); color: var(--danger); }
  .link {
    background: none; border: 0; padding: 0; font: inherit; font-weight: 650;
    color: var(--accent); cursor: pointer; text-decoration: underline;
  }
</style>
