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

<h2>Personalisation</h2>

<section class="card">
  <h3>Theme</h3>
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

<section class="card">
  <h3>Layout &amp; type</h3>
  <label>
    Layout spacing
    <select value={spacing} onchange={(e) => save({ "personalisation.spacing": e.currentTarget.value })}>
      <option value="compact">Compact</option>
      <option value="comfortable">Comfortable</option>
      <option value="spacious">Spacious</option>
    </select>
  </label>
  <label>
    Font
    <select value={font} onchange={(e) => save({ "personalisation.font": e.currentTarget.value })}>
      <option value="sans">Manrope (default)</option>
      <option value="system">System</option>
      <option value="mono">Monospace</option>
    </select>
  </label>
  <p class="sub">Spacing and font apply to the whole app once the save is confirmed.</p>
</section>

<style>
  .row {
    display: flex;
    gap: var(--space-2);
  }
  .opt {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-2);
    background: var(--bg);
    cursor: pointer;
  }
  .opt.selected {
    border-color: var(--accent);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    max-width: 20rem;
    margin-top: var(--space-2);
  }
  .sub {
    color: var(--text-2);
  }
</style>
