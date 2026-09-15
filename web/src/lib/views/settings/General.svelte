<script lang="ts">
  import {
    TIMEZONE_KEY,
    localTimeIn,
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
   */

  let { settings, save }: {
    settings: Record<string, unknown>;
    save: (p: Record<string, unknown>) => void;
  } = $props();

  const language = $derived((settings["general.language"] as string) ?? "en-GB");
  const region = $derived((settings["general.region"] as string) ?? "GB");
  const startupRoute = $derived((settings["general.startup_route"] as string) ?? "workbench");
  const speechLanguage = $derived((settings["general.speech_language"] as string) ?? "auto");

  // The time zone is not a formatting preference here. It is the one
  // owner-level value every model turn reasons from, so the control shows what
  // is actually in force, where that came from, and what the owner's clock reads
  // in it right now. A select whose effect you cannot see is a select nobody
  // trusts.
  const zones = timezoneOptions();
  const resolved = $derived(resolvedTimezone(settings));
  const explicit = $derived((settings[TIMEZONE_KEY] as string) ?? "");
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
</script>

<header class="section-heading">
  <h2>General</h2>
</header>

<section class="settings-card" aria-labelledby="language-region">
  <div class="card-heading">
    <h3 id="language-region">Language and region</h3>
    <p>Interface text and formatting only. These do not change what Raiker tells a model.</p>
  </div>
  <label>
    <span>Speech language</span>
    <small>Dictation and read-aloud, in Chat and Build.</small>
    <select aria-label="Speech language" value={speechLanguage} onchange={(e) => save({ "general.speech_language": e.currentTarget.value })}>
      <option value="auto">Auto (device language)</option>
      <option value="en">English</option>
      <option value="fr">Français</option>
      <option value="de">Deutsch</option>
      <option value="hi">हिन्दी</option>
      <option value="it">Italiano</option>
      <option value="ja">日本語</option>
      <option value="ko">한국어</option>
      <option value="pt">Português</option>
      <option value="ru">Русский</option>
      <option value="es">Español</option>
      <option value="tr">Türkçe</option>
      <option value="uk">Українська</option>
    </select>
  </label>
  <label>
    <span>Language</span>
    <select value={language} onchange={(e) => save({ "general.language": e.currentTarget.value })}>
      <option value="en-GB">English (United Kingdom)</option>
      <option value="en-US">English (United States)</option>
      <option value="hi-IN">हिन्दी (भारत)</option>
      <option value="es-ES">Español (España)</option>
      <option value="fr-FR">Français (France)</option>
      <option value="de-DE">Deutsch (Deutschland)</option>
    </select>
  </label>
  <label>
    <span>Country or region</span>
    <small>Formatting only. Scheduling is decided under Time and place.</small>
    <select value={region} onchange={(e) => save({ "general.region": e.currentTarget.value })}>
      <option value="GB">United Kingdom</option>
      <option value="US">United States</option>
      <option value="IN">India</option>
      <option value="DE">Germany</option>
      <option value="FR">France</option>
      <option value="ES">Spain</option>
    </select>
  </label>
</section>

<section class="settings-card" aria-labelledby="time-and-place">
  <div class="card-heading">
    <h3 id="time-and-place">Time and place</h3>
    <p>Every model turn is told the date, day and time in this zone. No web connection needed.</p>
  </div>
  <label>
    <span>Time zone</span>
    <small>
      Used for schedules, recurring tasks and every relative instruction — tomorrow,
      tonight, this Friday.
    </small>
    <select
      aria-label="Time zone"
      value={explicit}
      onchange={(e) => save({ [TIMEZONE_KEY]: e.currentTarget.value })}
    >
      <option value="">Not set — Raiker falls back to UTC</option>
      {#each zones as zone (zone)}
        <option value={zone}>{zone}</option>
      {/each}
    </select>
  </label>
  <p class="resolved" data-testid="timezone-resolved">
    <strong>{resolved.zone}</strong> · {timezoneSourceLabel(resolved.source)}
    {#if sample}<br /><span class="clock">Right now that reads {sample}.</span>{/if}
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
</section>

<section class="settings-card" aria-labelledby="startup-behaviour">
  <div class="card-heading">
    <h3 id="startup-behaviour">Startup behaviour</h3>
    <p>The first page Raiker opens. Links and bookmarks are unaffected.</p>
  </div>
  <label>
    <span>Default startup view</span>
    <select value={startupRoute} onchange={(e) => save({ "general.startup_route": e.currentTarget.value })}>
      <option value="workbench">Workbench</option>
      <option value="new-chat">New chat</option>
      <option value="tasks">Tasks</option>
      <option value="projects">Projects</option>
      <option value="approvals">Approvals</option>
      <option value="last-visited">Last visited page</option>
    </select>
  </label>
</section>

<style>
  .section-heading { margin-bottom: var(--space-4); }
  .section-heading h2, .card-heading h3 { margin: 0; }
  .card-heading p { color: var(--text-2); margin: .3rem 0 0; }
  .settings-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: var(--card-pad-y) var(--card-pad-x); margin-bottom: var(--space-4); }
  label { display: grid; gap: .3rem; max-width: 34rem; margin-top: var(--space-5); font-weight: 650; }
  label small { color: var(--text-2); font-weight: 400; }
  select { width: 100%; }
  .resolved { color: var(--text-2); margin: var(--space-3) 0 0; max-width: 34rem; }
  .resolved strong { color: var(--text-1); }
  .clock { font-variant-numeric: tabular-nums; }
  .proposal { color: var(--text-2); margin: var(--space-2) 0 0; max-width: 34rem; }
  .proposal strong { color: var(--text-1); }
  .link {
    background: none; border: 0; padding: 0; font: inherit; font-weight: 650;
    color: var(--accent); cursor: pointer; text-decoration: underline;
  }
</style>
