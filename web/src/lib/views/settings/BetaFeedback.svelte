<script lang="ts">
  /**
   * Beta feedback, from inside Raiker (beta plan DOC-4).
   *
   * Two links to the repository's issue forms, prefilled with the build and a
   * coarse operating system, and a button that copies the redacted support
   * bundle for the owner to paste if they want to. Raiker itself sends
   * nothing: the owner reads every field on GitHub before submitting.
   */
  import { onMount } from "svelte";
  import { api, ApiError } from "../../api";
  import { clientBuild, describeBuild } from "../../buildIdentity";
  import { detectOs, issueUrl, type FeedbackEnvironment } from "../../betaFeedback";

  let host = $state<string | null>(null);
  let copyState = $state<"idle" | "copying" | "copied" | "failed" | "blocked">("idle");

  const environment = $derived<FeedbackEnvironment>({
    host: host ?? describeBuild(clientBuild, null),
    client: describeBuild(clientBuild, null),
    os: detectOs(),
  });
  const bugUrl = $derived(issueUrl("bug", environment));
  const feedbackUrl = $derived(issueUrl("feedback", environment));

  onMount(async () => {
    try {
      const update = await api.hostUpdate();
      host = describeBuild(update.installation.version, update.installation.commit);
    } catch {
      host = null; // the page's own build stands in; the form says which it is
    }
  });

  async function copyDiagnostics() {
    copyState = "copying";
    try {
      const bundle = await api.diagnosticsExport();
      await navigator.clipboard.writeText(JSON.stringify(bundle, null, 2));
      copyState = "copied";
    } catch (error) {
      copyState =
        error instanceof ApiError && error.reasonCode === "support_export_blocked" ? "blocked" : "failed";
    }
  }
</script>

<section class="settings-card" aria-labelledby="beta-feedback">
  <div class="card-heading">
    <h3 id="beta-feedback">Beta feedback</h3>
    <p>
      This is a beta. Tell us what broke or what could be better — each link opens a short form on GitHub in
      your browser, already filled in with this build and your operating system. Raiker sends nothing itself;
      you see every field before you submit, and the issue is public.
    </p>
  </div>
  <dl class="facts">
    <div><dt>Build</dt><dd data-feedback-build>{environment.host}</dd></div>
    <div><dt>System</dt><dd>{environment.os}</dd></div>
  </dl>
  <div class="actions">
    <a class="btn btn-primary btn-sm" href={bugUrl} target="_blank" rel="noopener noreferrer">Report a problem</a>
    <a class="btn btn-ghost btn-sm" href={feedbackUrl} target="_blank" rel="noopener noreferrer">Suggest an improvement</a>
    <button class="btn btn-ghost btn-sm" type="button" onclick={copyDiagnostics} disabled={copyState === "copying"}>
      {copyState === "copying" ? "Preparing…" : "Copy diagnostics"}
    </button>
  </div>
  <p class="note" role="status" aria-live="polite">
    {#if copyState === "copied"}
      Copied. It is the redacted support bundle from Diagnostics — read it before pasting it into an issue.
    {:else if copyState === "blocked"}
      Not copied: after redaction something still looked like a secret, so Raiker did not build the bundle.
    {:else if copyState === "failed"}
      The diagnostics could not be copied. You can open them under Diagnostics → Support bundle.
    {:else}
      Diagnostics are optional and never added to the link. A security problem? Follow SECURITY.md instead of
      opening a public issue.
    {/if}
  </p>
</section>

<style>
  .facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.5rem; margin: 0.5rem 0; }
  dt { color: var(--text-3); font-size: var(--text-xs); font-weight: 650; }
  dd { margin: 0.1rem 0 0; font-size: var(--text-sm); overflow-wrap: anywhere; }
  .actions { display: flex; flex-wrap: wrap; gap: 0.45rem; }
  .note { margin: 0.5rem 0 0; color: var(--text-3); font-size: var(--text-xs); }
  @media (max-width: 480px) { .facts { grid-template-columns: 1fr; } }
</style>
