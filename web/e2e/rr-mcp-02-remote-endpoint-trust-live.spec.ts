/**
 * RR-MCP-02, live: where a remote MCP server may live, and what Raiker says
 * about it.
 *
 * Adding a remote server used to be one scheme check. Five different
 * destinations were indistinguishable from each other — the owner's own
 * machine, a box on their LAN, a public endpoint, a public name that answers
 * with a private address, and a cloud metadata service that hands out the
 * credentials of the machine Raiker is running on — and every one of them read
 * as "Remote (HTTPS)" on the card while the owner's bearer token went to all
 * five the same way.
 *
 * Two halves are asserted here, and the first matters as much as the second:
 * Raiker is owner-authoritative and monitored, so a local tool server over
 * plain http still connects and a LAN address is still the owner's own choice.
 * What is refused is the narrow set where the destination is not the thing the
 * owner typed — and each refusal arrives as a sentence, not as the reason code
 * that used to reach the screen.
 */
import { expect, test, type Page } from "@playwright/test";
import { capture } from "./capture";
import { signInAsOwner } from "./hosted-provider";

const BASE = "http://127.0.0.1:8765";
const SHOTS = "../../docs/screenshots/2026-09-13-mcp-endpoint-trust";

/** Open Extensions → MCP servers, signed in. */
async function mcpTab(page: Page): Promise<void> {
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/extensions?tab=mcp`);
  await expect(page.getByRole("tabpanel", { name: "MCP servers" })).toBeVisible({
    timeout: 30_000,
  });
}

/**
 * Add a remote server through the API the page calls, and return what came
 * back. The Add flow lives in Connections; this asserts the boundary rather
 * than the form, so it goes through the same governed route the form does.
 */
async function addRemote(
  page: Page,
  name: string,
  endpoint: string,
): Promise<{ status: number; reason: string | null }> {
  return page.evaluate(
    async ([serverName, endpointUrl]) => {
      const csrf = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/)?.[1];
      const response = await fetch("/api/mcp/servers/remote", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(csrf ? { "X-Raiker-CSRF": decodeURIComponent(csrf) } : {}),
        },
        body: JSON.stringify({ name: serverName, endpoint_url: endpointUrl }),
      });
      const body = (await response.json().catch(() => null)) as {
        detail?: { reason_code?: string };
      } | null;
      return { status: response.status, reason: body?.detail?.reason_code ?? null };
    },
    [name, endpoint] as const,
  );
}

test("the owner's own machine and their own network are still theirs", async ({ page }) => {
  test.setTimeout(180_000);
  await mcpTab(page);

  // A local MCP server over plain http is the ordinary case, not a threat.
  const local = await addRemote(page, "local tools", "http://127.0.0.1:8931/mcp");
  expect(local.status, JSON.stringify(local)).toBe(200);

  // A NAS or a workstation running a tool server is a thing owners have.
  const lan = await addRemote(page, "nas tools", "http://192.168.1.20:3000/mcp");
  expect(lan.status, JSON.stringify(lan)).toBe(200);

  // A public endpoint, over TLS, is accepted without being resolved here: a
  // server that is not up yet is not a reason to refuse the URL being typed.
  const remote = await addRemote(page, "public tools", "https://tools.example.com/mcp");
  expect(remote.status, JSON.stringify(remote)).toBe(200);

  await page.reload();
  await expect(page.getByRole("tabpanel", { name: "MCP servers" })).toBeVisible({
    timeout: 30_000,
  });

  // The card used to print "Remote (HTTPS)" over all three. It now says which
  // of the three destinations this is, and whether the wire is encrypted.
  await expect(page.getByText("This machine (unencrypted HTTP)")).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("Your network (unencrypted HTTP)")).toBeVisible();
  await expect(page.getByText("Remote (HTTPS)")).toBeVisible();

  await capture(page, `${SHOTS}/mcp-destinations-named.png`);
});

test("a destination that is not the one the owner typed is refused, in words", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await mcpTab(page);

  // Each of these is refused for a different reason, and the reason is the
  // point: a cloud metadata service answers with the credentials of the host,
  // a public endpoint over plain http puts the owner's token on the wire in
  // clear text, and a credential inside a URL is a credential in every log
  // that ever prints it.
  const refusals: Array<[string, string, string]> = [
    ["metadata", "http://169.254.169.254/latest/meta-data/", "mcp_remote_link_local"],
    ["gcp metadata", "http://metadata.google.internal/mcp", "mcp_remote_metadata_endpoint"],
    ["cleartext", "http://tools.example.com/mcp", "mcp_remote_requires_https"],
    [
      "inline credential",
      "https://user:secret@tools.example.com/mcp",
      "mcp_remote_endpoint_credentials",
    ],
  ];
  for (const [name, endpoint, reason] of refusals) {
    const result = await addRemote(page, name, endpoint);
    expect(result.status, `${endpoint}: ${JSON.stringify(result)}`).toBe(422);
    expect(result.reason, endpoint).toBe(reason);
  }

  // None of them became a stored server that looks added and fails at first use.
  const stored = await page.evaluate(async () => {
    const response = await fetch("/api/mcp/servers");
    return ((await response.json()) as Array<{ name: string }>).map((s) => s.name);
  });
  for (const [name] of refusals) expect(stored).not.toContain(name);
});

test("the Add form says what the endpoint is while it is being typed", async ({ page }) => {
  test.setTimeout(180_000);
  await signInAsOwner(page, BASE);
  await page.goto(`${BASE}/#/connections`);

  const mcpButton = page.getByRole("button", { name: /^Connect .+ via MCP$/ }).first();
  await expect(mcpButton).toBeVisible({ timeout: 60_000 });
  await mcpButton.click();

  // The remote half of the dialog only exists once the transport is remote.
  await page.getByRole("radio", { name: "Remote MCP server" }).check();

  const endpoint = page.getByLabel("MCP endpoint URL");
  await expect(endpoint).toBeVisible({ timeout: 30_000 });
  await endpoint.fill("http://127.0.0.1:8931/mcp");
  await expect(page.getByText("This machine (unencrypted HTTP)")).toBeVisible();

  await endpoint.fill("https://tools.example.com/mcp");
  await expect(page.getByText("Remote (HTTPS)")).toBeVisible();

  await capture(page, `${SHOTS}/mcp-add-endpoint-class.png`);
});
