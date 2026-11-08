import { expect, it } from "vitest";
import { GITHUB_APP_PERMISSIONS, githubAppRegistrationUrl, suggestedAppName } from "./githubAppLink";

it("pre-fills GitHub's own registration form with only the permissions Raiker needs", () => {
  const url = new URL(githubAppRegistrationUrl("http://127.0.0.1:8765/", "Raiker test"));
  expect(`${url.origin}${url.pathname}`).toBe("https://github.com/settings/apps/new");
  const q = url.searchParams;
  expect(q.get("name")).toBe("Raiker test");
  expect(q.getAll("callback_urls[]")).toEqual(["http://127.0.0.1:8765/api/github/callback"]);
  expect(q.get("public")).toBe("false");
  expect(q.get("webhook_active")).toBe("false");
  expect(Object.fromEntries(Object.keys(GITHUB_APP_PERMISSIONS).map((k) => [k, q.get(k)]))).toEqual({
    contents: "write", pull_requests: "write", issues: "read", metadata: "read",
  });
  // Nothing else is asked for: no workflows, no administration, no secrets.
  for (const wider of ["workflows", "administration", "secrets", "actions"]) expect(q.has(wider)).toBe(false);
});

it("suggests a fresh name, because GitHub App names are unique across GitHub", () => {
  expect(suggestedAppName(() => 0)).toBe("Raiker 0000");
  expect(suggestedAppName(() => 0.5)).toMatch(/^Raiker [0-9a-z]{4}$/);
});
