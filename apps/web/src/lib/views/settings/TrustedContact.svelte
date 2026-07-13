<script lang="ts">
  import NotYetActive from "./NotYetActive.svelte";

  interface Contact {
    name: string;
    method: string;
    value: string;
  }

  let { settings, save }: { settings: Record<string, unknown>; save: (p: Record<string, unknown>) => void } =
    $props();

  const contacts = $derived(((settings["trusted.contacts"] as Contact[]) ?? []) as Contact[]);

  let name = $state("");
  let method = $state("email");
  let value = $state("");

  function add() {
    if (!name.trim() || !value.trim()) return;
    save({ "trusted.contacts": [...contacts, { name, method, value }] });
    name = "";
    value = "";
  }
  function remove(index: number) {
    save({ "trusted.contacts": contacts.filter((_, i) => i !== index) });
  }
</script>

<h2>Trusted Contact</h2>

<section class="card">
  <h3>Recovery contacts</h3>
  {#if contacts.length === 0}
    <p class="sub">No recovery contacts yet.</p>
  {:else}
    <ul class="contacts">
      {#each contacts as c, i (i)}
        <li>
          <span><strong>{c.name}</strong> · {c.method}: {c.value}</span>
          <button type="button" class="btn btn-danger" onclick={() => remove(i)}>Remove</button>
        </li>
      {/each}
    </ul>
  {/if}
  <div class="add">
    <input placeholder="Name" bind:value={name} aria-label="Contact name" />
    <select bind:value={method} aria-label="Contact method">
      <option value="email">Email</option>
      <option value="phone">Phone</option>
    </select>
    <input placeholder="Email or phone" bind:value aria-label="Contact value" />
    <button type="button" class="btn btn-primary" onclick={add}>Add</button>
  </div>
  <p class="sub">Recovery contacts are saved to your account.</p>
</section>

<section class="card">
  <h3>Emergency access</h3>
  <NotYetActive what="Emergency-access protocols and shared permissions" />
</section>

<style>
  .contacts {
    list-style: none;
    padding: 0;
  }
  .contacts li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-1) 0;
  }
  .add {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-top: var(--space-2);
  }
  .sub {
    color: var(--text-2);
  }
</style>
