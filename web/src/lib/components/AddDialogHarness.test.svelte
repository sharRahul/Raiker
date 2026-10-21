<script lang="ts">
  import AddDialog from "./AddDialog.svelte";

  let { onclose = (() => {}) as () => void, chosen = null as string | null } = $props();
  const options = [
    { id: "gmail", name: "Gmail", description: "Read and draft email", category: "Mail" },
    { id: "slack", name: "Slack", description: "Read channels", category: "Chat" },
    { id: "github", name: "GitHub", description: "Repositories", category: "Code", note: "Connected" },
  ];
</script>

<AddDialog title="Add connection" {options} {chosen} searchLabel="Search services" {onclose}>
  {#snippet steps(option)}<p>Steps for {option.name}</p>{/snippet}
</AddDialog>
