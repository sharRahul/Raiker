<script lang="ts">
  /**
   * BR-D02 — where a Build turn on this repository would actually run.
   *
   * A repository name is not a target. The chip states the facts a turn is
   * bound to — the branch and commit, and where code such as a test run would
   * execute — read from the server's own description of the target, never
   * inferred in the browser. Its full detail (folder, repository identity,
   * command environment, fingerprint) is the chip's accessible name and
   * tooltip, so the header stays one line.
   *
   * A folder that has gone is said by the header's own warning; a GitHub
   * coordinate has no checkout, and the chip says so instead of a branch.
   *
   * BR-01 — the chip also says what a turn here may do *without asking*: the
   * repository delegation it would act under (operations, branch pattern,
   * expiry) or, with none, that every repository write asks first. Merging is
   * never delegable and the chip says so.
   */
  import { api } from "../api";
  import type { CodeRepoTargetView } from "../generated/apiContract";
  import Icon from "./Icon.svelte";

  let { repoId, revision = 0 }: { repoId: string | null; revision?: number } = $props();

  let target = $state<CodeRepoTargetView | null>(null);

  $effect(() => {
    const id = repoId;
    void revision;
    target = null;
    if (id === null) return;
    let cancelled = false;
    api
      .readCodeRepoTarget(id)
      .then((value) => {
        if (!cancelled) target = value;
      })
      .catch(() => {
        // No description is not a claim about the target; the chip stays absent.
      });
    return () => {
      cancelled = true;
    };
  });

  const PLACEMENT: Record<string, string> = {
    sandbox: "Sandbox",
    unavailable: "Sandbox unavailable",
    host_network: "This computer",
    owner_environment: "Your environment",
    not_code: "This computer",
  };

  const where = $derived(
    target === null
      ? ""
      : target.host === "remote"
        ? "Remote environment"
        : (PLACEMENT[target.code_placement] ?? "Unmeasured"),
  );

  const summary = $derived.by(() => {
    if (target === null) return "";
    if (target.state === "remote_only") return "GitHub · no checkout";
    if (!target.git) return "No git history";
    const branch = target.branch || "detached";
    return target.head ? `${branch} · ${target.head}` : branch;
  });

  const OPERATION: Record<string, string> = {
    push: "push",
    branch: "branch",
    commit: "commit",
    pull_request: "pull request",
  };

  const delegations = $derived(target?.authority?.delegations ?? []);
  const onGitHub = $derived(Boolean(target?.authority?.repository));

  const delegated = $derived.by(() => {
    if (!onGitHub) return "";
    if (delegations.length === 0) return "Writes ask you";
    const first = delegations[0];
    const operations = first.operations.map((item) => OPERATION[item] ?? item).join(", ");
    return `Delegated: ${operations}${first.branch_pattern ? ` on ${first.branch_pattern}` : ""}`;
  });

  const detail = $derived.by(() => {
    if (target === null) return "";
    const lines = [
      `Folder: ${target.folder}`,
      `Repository: ${target.identity || "not recorded"}`,
      `Branch: ${target.branch || (target.git ? "detached" : "none")}`,
      `Commands run in: ${target.environment || "unknown"} (${where})`,
      `Target fingerprint: ${target.fingerprint.slice(0, 12)}`,
    ];
    if (onGitHub) {
      if (delegations.length === 0) {
        lines.push("Delegation: none — every push, branch, commit and pull request asks you first");
      }
      for (const item of delegations) {
        const operations = item.operations.map((op) => OPERATION[op] ?? op).join(", ");
        const left = item.actions_left === null ? "" : `, ${item.actions_left} action${item.actions_left === 1 ? "" : "s"} left`;
        lines.push(
          `Delegation: ${operations}${item.branch_pattern ? ` on ${item.branch_pattern}` : ""}` +
            `${item.allow_pull_request ? ", may open a pull request" : ""}, until ${item.expires_at}${left}`,
        );
      }
      lines.push("Merging is never delegated: it stays with you, on GitHub");
      if (target.authority && !target.authority.git_credential) lines.push("Git credential: none selected");
    }
    return lines.join("\n");
  });
</script>

{#if target !== null && target.state !== "folder_missing" && target.state !== "no_repository"}
  <span
    class="target-chip"
    data-testid="build-target"
    data-state={target.state}
    title={detail}
    aria-label={`Build target. ${detail.replaceAll("\n", ". ")}`}
    role="note"
  >
    <Icon name="branch" size="sm" />
    <span class="summary">{summary}</span>
    <span class="where" data-placement={target.code_placement}>{where}</span>
    {#if delegated}
      <span class="delegated" data-delegated={delegations.length > 0 ? "yes" : "no"}>{delegated}</span>
    {/if}
  </span>
{/if}

<style>
  .target-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-width: 0;
    padding: 0.15rem 0.55rem;
    border: 1px solid var(--neutral-border);
    border-radius: var(--r-pill);
    background: var(--surface);
    color: var(--text-2);
    font-size: var(--text-xs);
    white-space: nowrap;
  }
  .summary {
    font-family: var(--font-mono);
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .where {
    padding-left: 0.35rem;
    border-left: 1px solid var(--neutral-border);
    color: var(--text-3);
  }
  .where[data-placement="sandbox"] {
    color: var(--ok);
  }
  .delegated {
    padding-left: 0.35rem;
    border-left: 1px solid var(--neutral-border);
    color: var(--text-3);
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .delegated[data-delegated="yes"] {
    color: var(--text-2);
  }
  @media (max-width: 640px) {
    .where,
    .delegated {
      display: none;
    }
  }
</style>
