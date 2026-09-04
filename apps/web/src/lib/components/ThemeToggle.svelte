<script lang="ts">
  import Icon from "./Icon.svelte";
  import {
    applyTheme,
    loadThemeChoice,
    saveThemeChoice,
    type ThemeChoice,
  } from "../theme";

  // Cycle light → dark → system. The current choice is announced via aria-label.
  let choice = $state<ThemeChoice>(loadThemeChoice());

  const NEXT: Record<ThemeChoice, ThemeChoice> = { light: "dark", dark: "system", system: "light" };
  const ICONS = { light: "sun", dark: "moon", system: "system" } as const;
  const LABELS: Record<ThemeChoice, string> = {
    light: "Theme: light. Switch to dark.",
    dark: "Theme: dark. Switch to system.",
    system: "Theme: system. Switch to light.",
  };

  function cycle() {
    choice = NEXT[choice];
    applyTheme(choice);
    saveThemeChoice(choice);
  }
</script>

<button type="button" class="btn btn-ghost theme-toggle" onclick={cycle} aria-label={LABELS[choice]}>
  <Icon name={ICONS[choice]} size="md" />
  <span class="choice-label">{choice}</span>
</button>

<style>
  .theme-toggle {
    text-transform: capitalize;
  }
  .choice-label {
    font-size: 0.8rem;
  }
</style>
