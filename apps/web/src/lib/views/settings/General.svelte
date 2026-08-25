<script lang="ts">
  let { settings, save }: {
    settings: Record<string, unknown>;
    save: (p: Record<string, unknown>) => void;
  } = $props();

  const language = $derived((settings["general.language"] as string) ?? "en-GB");
  const region = $derived((settings["general.region"] as string) ?? "GB");
  const timezone = $derived((settings["general.timezone"] as string) ?? "Europe/London");
  const startupRoute = $derived((settings["general.startup_route"] as string) ?? "workbench");
  const speechLanguage = $derived((settings["general.speech_language"] as string) ?? "auto");
</script>

<header class="section-heading">
  <h2>General</h2>
  <p>Choose how Raiker displays information and where your day begins.</p>
</header>

<section class="settings-card" aria-labelledby="language-region">
  <div class="card-heading">
    <h3 id="language-region">Language and region</h3>
    <p>These preferences control interface text, dates, times, and regional formatting.</p>
  </div>
  <label>
    <span>Speech language</span>
    <small>Used for dictation and manual response read-aloud in both Chat and Build.</small>
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
    <small class="voice-disclosure">Raiker does not retain audio. Your browser's speech service may process audio externally.</small>
  </label>
  <label>
    <span>Language</span>
    <small>Controls the language used throughout Raiker.</small>
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
    <small>Used for regional formatting. Scheduled work also uses the time zone below.</small>
    <select value={region} onchange={(e) => save({ "general.region": e.currentTarget.value })}>
      <option value="GB">United Kingdom</option>
      <option value="US">United States</option>
      <option value="IN">India</option>
      <option value="DE">Germany</option>
      <option value="FR">France</option>
      <option value="ES">Spain</option>
    </select>
  </label>
  <label>
    <span>Time zone</span>
    <small>Used for task schedules and activity timestamps.</small>
    <select value={timezone} onchange={(e) => save({ "general.timezone": e.currentTarget.value })}>
      <option value="Europe/London">Europe/London</option>
      <option value="America/New_York">America/New_York</option>
      <option value="America/Los_Angeles">America/Los_Angeles</option>
      <option value="Asia/Kolkata">Asia/Kolkata</option>
      <option value="Europe/Berlin">Europe/Berlin</option>
      <option value="UTC">UTC</option>
    </select>
  </label>
</section>

<section class="settings-card" aria-labelledby="startup-behaviour">
  <div class="card-heading">
    <h3 id="startup-behaviour">Startup behaviour</h3>
    <p>Choose the first page displayed when Raiker starts. Links and bookmarks are unaffected.</p>
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
  .section-heading p, .card-heading p { color: var(--text-2); margin: .3rem 0 0; }
  .settings-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: var(--card-pad-y) var(--card-pad-x); margin-bottom: var(--space-4); }
  label { display: grid; gap: .3rem; max-width: 34rem; margin-top: var(--space-5); font-weight: 650; }
  label small { color: var(--text-2); font-weight: 400; }
  .voice-disclosure { padding-left: .65rem; border-left: 2px solid var(--accent-border); }
  select { width: 100%; }
</style>
