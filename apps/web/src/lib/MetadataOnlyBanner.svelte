<script lang="ts">
  // Persistent banner shown on every approval surface (docs/UI-implementation/02_SECURITY_UX.md #8).
  // The copy must make the metadata-only limitation unmistakable.
</script>

<div class="metadata-banner" role="note">
  <span class="glyph" aria-hidden="true">ⓘ</span>
  <span>
    <strong>Approval resolution is metadata-only.</strong> Recording a decision does
    <strong>NOT</strong> execute the action.
  </span>
</div>

<style>
  .metadata-banner {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    border: 1px solid #2d5a82;
    background: #0f1f2e;
    color: #9cc7ec;
    border-radius: 8px;
    padding: 0.55rem 0.85rem;
    font-size: 0.85rem;
    margin: 0.75rem 0;
  }
  .glyph {
    font-weight: 700;
  }
</style>
