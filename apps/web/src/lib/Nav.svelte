<script lang="ts">
  import type { NavItem } from "./nav";

  let { items, current }: { items: NavItem[]; current: string } = $props();
</script>

<nav class="sidenav" aria-label="Primary">
  <ul>
    {#each items as item (item.id)}
      <li>
        <a href={"#/" + item.id} aria-current={current === item.id ? "page" : undefined}>
          {item.label}
        </a>
      </li>
    {/each}
  </ul>
</nav>

<style>
  .sidenav {
    border-right: 1px solid #2a2a2e;
    padding: 0.75rem 0.5rem;
    min-width: 13rem;
    background: #0d0d10;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  a {
    display: block;
    padding: 0.45rem 0.6rem;
    border-radius: 6px;
    color: #c8c8cf;
    text-decoration: none;
    font-size: 0.9rem;
  }
  a:hover {
    background: #16161b;
  }
  a[aria-current="page"] {
    background: #1c2a3a;
    color: #cfe5ff;
    font-weight: 600;
  }
  a:focus-visible {
    outline: 2px solid #6aa9ff;
    outline-offset: 1px;
  }
</style>
