<script lang="ts">
  import ListDetail from "./ListDetail.svelte";

  let { items = [] as { id: string; name: string }[], selectedId = null as string | null } = $props();
</script>

<ListDetail
  {items}
  key={(item) => item.id}
  label="Things"
  matches={(item, query) => item.name.toLowerCase().includes(query)}
  searchLabel="Search things"
  {selectedId}
  syncAddress={true}
>
  {#snippet row(item)}<span>{item.name}</span>{/snippet}
  {#snippet detail(item)}<h2>{item.name} detail</h2>{/snippet}
  {#snippet empty()}<p>Nothing here yet.</p>{/snippet}
</ListDetail>
