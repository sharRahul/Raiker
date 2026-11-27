<script lang="ts">
  let {
    decision,
    disabled = false,
    busy = false,
    recordOnly = false,
    onclick,
  }: {
    decision: "approve" | "deny" | "task";
    disabled?: boolean;
    busy?: boolean;
    recordOnly?: boolean;
    onclick: () => void;
  } = $props();

  const label = $derived(
    decision === "deny" ? "Don't do this"
      : decision === "task" ? "Allow for this task…"
      : busy ? "Recording decision…"
      : recordOnly ? "Approve once (record only)" : "Approve once",
  );
</script>

<button type="button" class="btn btn-sm" class:btn-primary={decision === "approve"}
  disabled={disabled || busy} {onclick}>{label}</button>

<style>
  button { white-space: nowrap; }
</style>
