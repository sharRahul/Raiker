<script lang="ts">
  /**
   * BR-D05 — the repository's recent commits, and which of them Raiker made.
   *
   * A commit Raiker records carries `Raiker-Session` and `Raiker-Turn`
   * trailers. Anyone can type a trailer, so the server checks each against this
   * account's own records: **Made in Raiker** means the turn it names is one
   * Raiker here recorded; **Says Raiker — no record here** means the trailer is
   * there and nothing backs it. Evidence only: nothing reads it to allow
   * anything, and a commit without trailers is simply a commit.
   *
   * A commit the owner signed shows Git's own verdict on that signature
   * (**Signed**, **Signed — key not trusted here**, **Bad signature**…). Raiker
   * never signs a commit itself, so an unsigned commit shows nothing.
   */
  import { api } from "../api";
  import type { CodeRepoProvenanceView } from "../generated/apiContract";

  let { repoId, revision = 0 }: { repoId: string; revision?: number } = $props();

  let view = $state<CodeRepoProvenanceView | null>(null);

  $effect(() => {
    const id = repoId;
    void revision;
    let cancelled = false;
    api
      .readCodeRepoProvenance(id)
      .then((value) => {
        if (!cancelled) view = value;
      })
      .catch(() => {
        if (!cancelled) view = null;
      });
    return () => {
      cancelled = true;
    };
  });

  const LABEL: Record<string, string> = {
    recorded: "Made in Raiker",
    unrecorded: "Says Raiker — no record here",
    none: "",
  };

  const SIGNATURE: Record<string, string> = {
    good: "Signed",
    untrusted: "Signed — key not trusted here",
    bad: "Bad signature",
    expired: "Signed — key expired",
    revoked: "Signed — key revoked",
    unverifiable: "Signed — can't check here",
    none: "",
  };
</script>

{#if view && view.commits.length}
  <section class="recent-commits" aria-label="Recent commits" data-testid="recent-commits">
    <h3>Recent commits</h3>
    <ul>
      {#each view.commits.slice(0, 8) as commit (commit.commit)}
        <li data-provenance={commit.provenance}>
          <code class="sha">{commit.commit}</code>
          <span class="subject" title={commit.subject}>{commit.subject}</span>
          {#if commit.provenance !== "none"}
            <span
              class="badge"
              title={commit.turn_id ? `Turn ${commit.turn_id}` : commit.session_id ? `Conversation ${commit.session_id}` : ""}
            >
              {LABEL[commit.provenance]}
            </span>
          {/if}
          {#if commit.signature && commit.signature !== "none"}
            <span class="badge signature" data-signature={commit.signature}>{SIGNATURE[commit.signature]}</span>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  .signature[data-signature="bad"],
  .signature[data-signature="revoked"] {
    color: var(--danger);
    border-color: var(--danger-border);
  }
  .recent-commits {
    margin: var(--space-2) 0;
    font-size: var(--text-sm);
  }
  h3 {
    margin: 0 0 var(--space-1);
    font-size: var(--text-sm);
    font-weight: 650;
    color: var(--text-1);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.25rem;
  }
  li {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    min-width: 0;
    color: var(--text-2);
  }
  .sha {
    flex: none;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-3);
  }
  .subject {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .badge {
    flex: none;
    margin-left: auto;
    padding: 0.05rem 0.45rem;
    border-radius: var(--r-pill);
    border: 1px solid var(--neutral-border);
    font-size: var(--text-xs);
  }
  .badge + .badge {
    margin-left: 0;
  }
  li[data-provenance="recorded"] .badge:not(.signature) {
    border-color: var(--ok-border);
    background: var(--ok-soft);
    color: var(--ok);
  }
  li[data-provenance="unrecorded"] .badge {
    border-color: var(--warn-border);
    background: var(--warn-soft);
    color: var(--warn);
  }
</style>
