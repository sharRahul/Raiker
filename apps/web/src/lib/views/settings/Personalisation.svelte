<script lang="ts">
  import Icon from "../../components/Icon.svelte";
  import { applyTheme, loadThemeChoice, saveThemeChoice, type ThemeChoice } from "../../theme";

  let { settings, save }: { settings: Record<string, unknown>; save: (p: Record<string, unknown>) => void } =
    $props();

  let theme = $state<ThemeChoice>(loadThemeChoice());
  const THEME_OPTIONS: { value: ThemeChoice; label: string }[] = [
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
    { value: "system", label: "System" },
  ];
  function chooseTheme(value: ThemeChoice) {
    theme = value;
    applyTheme(value);
    saveThemeChoice(value);
  }

  const spacing = $derived((settings["personalisation.spacing"] as string) ?? "comfortable");
  const font = $derived((settings["personalisation.font"] as string) ?? "sans");
</script>

<header class="section-heading">
  <h2>Personalisation</h2>
  <p>Choose how Raiker looks and how much information fits on screen.</p>
</header>

<section class="settings-card">
  <div class="card-heading"><h3>Theme</h3><p>Choose a light or dark appearance, or follow your device.</p></div>
  <div class="row" role="radiogroup" aria-label="Theme">
    {#each THEME_OPTIONS as option (option.value)}
      <button
        type="button"
        class="opt"
        class:selected={theme === option.value}
        role="radio"
        aria-checked={theme === option.value}
        onclick={() => chooseTheme(option.value)}
      >
        <Icon name={option.value === "light" ? "sun" : option.value === "dark" ? "moon" : "system"} size={16} />
        {option.label}
      </button>
    {/each}
  </div>
</section>

<section class="settings-card">
  <div class="card-heading"><h3>Layout &amp; type</h3><p>Adjust interface density and the primary typeface.</p></div>
  <label>
    <span>Layout spacing</span>
    <small>Controls the density of lists, cards, and forms throughout Raiker.</small>
    <select class="settings-select" aria-label="Layout spacing" value={spacing} onchange={(e) => save({ "personalisation.spacing": e.currentTarget.value })}>
      <option value="compact">Compact</option>
      <option value="comfortable">Comfortable</option>
      <option value="spacious">Spacious</option>
    </select>
  </label>
  <label>
    <span>Font</span>
    <small>Choose the typeface used across the interface.</small>
    <select class="settings-select" aria-label="Font" value={font} onchange={(e) => save({ "personalisation.font": e.currentTarget.value })}>
      <option value="sans">Manrope (default)</option>
      <option value="system">System</option>
      <option value="mono">Monospace</option>
    </select>
  </label>
</section>

<style>
  .section-heading { margin-bottom:var(--space-4); }
  .section-heading h2,.card-heading h3 { margin:0; }
  .section-heading p,.card-heading p { color:var(--text-2); margin:.3rem 0 0; }
  .settings-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-lg); padding:clamp(1.25rem, 3vw, 2rem); margin-bottom:var(--space-4); }
  .row {
    display: flex;
    gap: var(--space-2);
    margin-top:var(--space-5);
    flex-wrap:wrap;
  }
  .opt {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    min-height:44px;
    border-radius: var(--r-md);
    background: var(--surface);
    color:var(--text-1);
    font:inherit;
    cursor: pointer;
  }
  .opt.selected {
    border-color: var(--accent);
  }
  label {
    display:grid;
    gap:.3rem;
    max-width:34rem;
    margin-top:var(--space-5);
    font-weight:650;
  }
  label small { color:var(--text-2); font-weight:400; }
  .settings-select { width:100%; min-height:44px; padding:0 .8rem; border:1px solid var(--border-strong); border-radius:var(--r-md); background:var(--surface); color:var(--text-1); font:inherit; }
  .settings-select:focus-visible,.opt:focus-visible { outline:3px solid var(--focus-ring); outline-offset:2px; }
</style>
