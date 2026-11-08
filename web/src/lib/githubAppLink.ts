/**
 * The one-click registration of the owner's own GitHub App.
 *
 * GitHub pre-fills its "Register new GitHub App" form from URL parameters
 * ("Registering a GitHub App using URL parameters"). The owner checks the form
 * and clicks Create; nothing is registered until they do. The permissions are
 * exactly what Raiker's GitHub features need (GITHUB_CONNECTION_SPEC §8), and
 * no more:
 *
 *  - Contents: write, to push an authorised branch;
 *  - Pull requests: write, to open or update a pull request;
 *  - Issues: read, for issue-to-PR;
 *  - Metadata: read, which GitHub grants with any repository permission.
 *
 * Webhooks stay off, and the App is private to the owner's account.
 */

export const GITHUB_APP_PERMISSIONS = {
  contents: "write",
  pull_requests: "write",
  issues: "read",
  metadata: "read",
} as const;

/** GitHub App names are unique across GitHub, so each link suggests a fresh one. */
export function suggestedAppName(random: () => number = Math.random): string {
  const suffix = Math.floor(random() * 36 ** 4).toString(36).padStart(4, "0");
  return `Raiker ${suffix}`;
}

export function githubAppRegistrationUrl(origin: string, name: string = suggestedAppName()): string {
  const base = origin.replace(/\/+$/, "");
  const params = new URLSearchParams();
  params.set("name", name);
  params.set("description", "My own Raiker: reads issues, pushes branches and opens pull requests I approve.");
  params.set("url", "https://github.com/sharRahul/Raiker");
  params.append("callback_urls[]", `${base}/api/github/callback`);
  params.set("request_oauth_on_install", "false");
  params.set("public", "false");
  params.set("webhook_active", "false");
  for (const [permission, access] of Object.entries(GITHUB_APP_PERMISSIONS)) params.set(permission, access);
  return `https://github.com/settings/apps/new?${params.toString()}`;
}
