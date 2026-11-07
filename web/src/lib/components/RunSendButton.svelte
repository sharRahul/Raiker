<script lang="ts">
  /*
   * 03 Composer execution states — one control in Send's place.
   *
   * At rest it is Send (or Build's posture word). While a turn runs it becomes
   * **Stop safely** while the prompt is empty, and **Queue** once something is
   * typed, so a follow-up is one press away and Stop is never a second button
   * competing with it. Stop is the governed interrupt in `RunningTurn`.
   */
  import Icon from "./Icon.svelte";
  import type { IconName } from "../icons";
  import type { RunningTurn } from "../runningTurn.svelte";

  let {
    streaming,
    hasText,
    control,
    label = "Send",
    icon = "arrow-up",
    disabled = false,
    title,
  }: {
    streaming: boolean;
    hasText: boolean;
    control: RunningTurn;
    /** The word at rest. */
    label?: string;
    icon?: IconName;
    /** Whether Send is unavailable at rest. Ignored while a turn runs. */
    disabled?: boolean;
    title?: string;
  } = $props();

  const mode = $derived(!streaming ? "send" : hasText ? "queue" : "stop");
</script>

{#if mode === "stop"}
  <button
    type="button"
    class="btn btn-danger send run-stop"
    data-mode="stop"
    onclick={() => void control.stop()}
    disabled={!control.ready || control.busy || control.stopping}
    title="Ends the turn at its next safe boundary and keeps what it has done"
  >
    <Icon name="stop" size="sm" />
    <span class="send-label">{control.stopping ? "Stopping…" : "Stop safely"}</span>
  </button>
{:else if mode === "queue"}
  <button
    type="submit"
    class="btn btn-primary send run-queue"
    data-mode="queue"
    disabled={control.busy}
    title="Queue this for the running turn — Raiker reads it at the next safe boundary"
  >
    <Icon name="clock" size="sm" />
    <span class="send-label">Queue</span>
  </button>
{:else}
  <button type="submit" class="btn btn-primary send" data-mode="send" {disabled} {title} aria-label={label}>
    <Icon name={icon} size="sm" />
    <span class="send-label">{label}</span>
  </button>
{/if}

<style>
  .run-stop, .run-queue { animation: morph 160ms ease-out 1; }
  @keyframes morph {
    from { transform: scale(0.92); opacity: 0.6; }
    to { transform: scale(1); opacity: 1; }
  }
  @media (prefers-reduced-motion: reduce) {
    .run-stop, .run-queue { animation: none; }
  }
</style>
