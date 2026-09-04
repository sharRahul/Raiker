<script lang="ts">
  import ProjectTreeNode from "./ProjectTreeNode.svelte";
  import type { ProjectTreeNode as TreeNode } from "../apiTypes";
  import Icon from "./Icon.svelte";

  let { node }: { node: TreeNode } = $props();

  let expanded = $state(false);
</script>

<li class="tree-node">
  <div class="node-row">
    {#if node.children.length > 0}
      <button type="button" class="expand-btn" onclick={() => (expanded = !expanded)} aria-label={expanded ? "Collapse" : "Expand"}>
        <Icon name={expanded ? "chevron-down" : "chevron-right"} size="sm" />
      </button>
    {:else}
      <span class="expand-placeholder"></span>
    {/if}
    <span class="node-label">{node.name}</span>
  </div>
  {#if expanded && node.children.length > 0}
    <ul class="children-list">
      {#each node.children as child (child.project_id)}
        <ProjectTreeNode node={child} />
      {/each}
    </ul>
  {/if}
</li>

<style>
  .tree-node {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .node-row {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.25rem 0;
    cursor: default;
  }
  .expand-btn {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    color: var(--text-2);
    display: inline-flex;
    align-items: center;
    width: 14px;
    height: 14px;
  }
  .expand-placeholder {
    display: inline-block;
    width: 14px;
    height: 14px;
  }
  .node-label {
    font-size: 0.88rem;
    overflow-wrap: anywhere;
  }
  .children-list {
    margin: 0 0 0 1.2rem;
    padding: 0;
  }
</style>
