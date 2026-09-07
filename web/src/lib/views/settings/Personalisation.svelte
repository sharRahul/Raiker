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

  // BUG-37 — density as a named mode with its consequence stated, rather than a
  // "Layout spacing" dropdown whose effect an owner had to discover by trying
  // it. The three options now reach control padding and row height as well as
  // the spacing scale, which is the part that makes Compact visible in a long
  // table instead of only in the gaps between cards.
  const DENSITY_OPTIONS: { value: string; label: string; detail: string }[] = [
    { value: "compact", label: "Compact", detail: "More rows on screen. Best for scanning tables and long lists." },
    { value: "comfortable", label: "Comfortable", detail: "The default. Balanced for reading and for acting." },
    { value: "spacious", label: "Spacious", detail: "More air around every control. Easiest on a touch screen." },
  ];
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
        <Icon name={option.value === "light" ? "sun" : option.value === "dark" ? "moon" : "system"} size="md" />
        {option.label}
      </button>
    {/each}
  </div>
</section>

<section class="settings-card">
  <div class="card-heading"><h3>Layout &amp; type</h3><p>Adjust interface density and the primary typeface.</p></div>
  <div class="density" role="radiogroup" aria-label="Density">
    <p class="density-lead">Density</p>
    <div class="density-options">
      {#each DENSITY_OPTIONS as option (option.value)}
        <button
          type="button"
          class="density-opt"
          class:selected={spacing === option.value}
          role="radio"
          aria-checked={spacing === option.value}
          onclick={() => save({ "personalisation.spacing": option.value })}
        >
          <span class="density-preview" data-density={option.value} aria-hidden="true">
            <i></i><i></i><i></i>
          </span>
          <strong>{option.label}</strong>
          <small>{option.detail}</small>
        </button>
      {/each}
    </div>
  </div>
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
  .settings-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-lg); padding:var(--card-pad-y) var(--card-pad-x); margin-bottom:var(--space-4); }
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
  .settings-select { width:100%; }
  .opt:focus-visible,.density-opt:focus-visible { outline:3px solid var(--focus-ring); outline-offset:2px; }

  /* Each option shows what it does. Three stacked rows at that mode's own row
     height is the smallest honest preview of a density setting — a name and a
     sentence still leave the owner to try it and see. */
  .density { margin-top: var(--space-5); }
  .density-lead { font-weight: 650; margin: 0 0 .3rem; }
  .density-options { display: grid; gap: var(--space-2); grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); }
  .density-opt {
    display: grid; gap: .2rem; text-align: left;
    padding: var(--space-3); border: 1px solid var(--border); border-radius: var(--r-md);
    background: var(--surface); color: var(--text-1); font: inherit; cursor: pointer;
    transition: border-color var(--motion-fast) var(--ease), background var(--motion-fast) var(--ease);
  }
  .density-opt:hover { border-color: var(--border-strong); }
  .density-opt.selected { border-color: var(--accent); background: var(--accent-soft); }
  .density-opt small { color: var(--text-2); font-weight: 400; font-size: var(--text-xs); }
  .density-preview { display: grid; gap: 3px; margin-bottom: .4rem; }
  .density-preview i { display: block; height: 6px; border-radius: 2px; background: var(--neutral-border); }
  .density-preview[data-density="compact"] { gap: 2px; }
  .density-preview[data-density="spacious"] { gap: 6px; }
  .density-preview i:last-child { width: 62%; }
</style>
