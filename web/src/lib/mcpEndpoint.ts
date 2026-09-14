/*
 * RR-MCP-02 — what a remote MCP server's address actually is, said on the card.
 *
 * Both surfaces that show a remote server printed "Remote (HTTPS)" for every
 * `http`-transport entry. That one label covered three different destinations —
 * the owner's own machine, a box on their own network, and a public endpoint —
 * and it covered them whether or not there was any TLS involved, so a server
 * reached over plain http read as encrypted.
 *
 * This module is the same classification the runtime makes
 * (`raiker/runtime/mcp_endpoint_policy.py`), done from the URL alone: it never
 * waits on a lookup, so a list of servers renders immediately and never changes
 * its mind while the owner is reading it. Whether a public *name* really
 * resolves to a public address is a question only the runtime can answer, and
 * it answers it when a session is about to run.
 *
 * It also carries the sentences for the endpoints the runtime refuses. Those
 * arrived on screen as their reason codes — `mcp_remote_host_not_public` is a
 * true statement and not one an owner can do anything with.
 */

export type McpNetworkClass = "loopback" | "private_network" | "public";

const LOOPBACK_NAMES = new Set(["localhost", "localhost.localdomain"]);
const METADATA_NAMES = new Set([
  "metadata.google.internal",
  "metadata.goog",
  "instance-data",
  "metadata",
]);
const PRIVATE_SUFFIXES = [".internal", ".lan", ".local", ".home.arpa"];

/** A dotted-quad or bracketed IPv6 literal, or null for a name. */
function literalAddress(host: string): string | null {
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(host)) return host;
  if (host.includes(":")) return host;
  return null;
}

function classifyIpv4(host: string): McpNetworkClass {
  const [a, b] = host.split(".").map((part) => Number(part));
  if (a === 127 || (a === 0 && b === 0)) return "loopback";
  if (a === 10) return "private_network";
  if (a === 172 && b >= 16 && b <= 31) return "private_network";
  if (a === 192 && b === 168) return "private_network";
  if (a === 169 && b === 254) return "private_network";
  return "public";
}

function classifyIpv6(host: string): McpNetworkClass {
  const text = host.toLowerCase();
  // An IPv4-mapped address is judged on the address it really carries: reading
  // only the outer form is a documented way past this kind of check. Both
  // spellings are handled, because `URL` rewrites the readable one
  // (`::ffff:127.0.0.1`) into the hex form (`::ffff:7f00:1`) before any of this
  // sees it — which is exactly how a check like this comes to miss.
  const dotted = /^::ffff:(\d{1,3}(?:\.\d{1,3}){3})$/.exec(text);
  if (dotted) return classifyIpv4(dotted[1]);
  const hex = /^::ffff:([0-9a-f]{1,4}):([0-9a-f]{1,4})$/.exec(text);
  if (hex) {
    const high = parseInt(hex[1], 16);
    const low = parseInt(hex[2], 16);
    return classifyIpv4(
      [high >> 8, high & 0xff, low >> 8, low & 0xff].join("."),
    );
  }
  if (text === "::1" || text === "::") return "loopback";
  if (text.startsWith("fe80") || text.startsWith("fc") || text.startsWith("fd"))
    return "private_network";
  return "public";
}

/**
 * The class an endpoint states, from the URL alone. `null` means it is not a
 * URL Raiker would accept at all.
 */
export function statedNetworkClass(endpointUrl: string | null | undefined): McpNetworkClass | null {
  if (!endpointUrl) return null;
  let url: URL;
  try {
    url = new URL(endpointUrl.trim());
  } catch {
    return null;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return null;
  const host = url.hostname.toLowerCase().replace(/\.$/, "").replace(/^\[|\]$/g, "");
  if (!host) return null;
  const literal = literalAddress(host);
  if (literal !== null) {
    return host.includes(":") ? classifyIpv6(host) : classifyIpv4(host);
  }
  if (LOOPBACK_NAMES.has(host)) return "loopback";
  if (METADATA_NAMES.has(host)) return "private_network";
  if (PRIVATE_SUFFIXES.some((suffix) => host.endsWith(suffix))) return "private_network";
  return "public";
}

/** Whether the endpoint is reached over TLS. */
export function endpointEncrypted(endpointUrl: string | null | undefined): boolean {
  return (endpointUrl ?? "").trim().toLowerCase().startsWith("https:");
}

/** The phrase on the card: where this server is, and whether the wire is encrypted. */
export function networkClassLabel(endpointUrl: string | null | undefined): string {
  const networkClass = statedNetworkClass(endpointUrl);
  if (networkClass === null) return "Remote (unrecognised endpoint)";
  const suffix = endpointEncrypted(endpointUrl) ? "HTTPS" : "unencrypted HTTP";
  if (networkClass === "loopback") return `This machine (${suffix})`;
  if (networkClass === "private_network") return `Your network (${suffix})`;
  return `Remote (${suffix})`;
}

const ENDPOINT_REFUSALS: Record<string, string> = {
  mcp_remote_invalid_endpoint:
    "That is not an MCP endpoint Raiker can reach. Use an http or https URL with a host, for example https://tools.example.com/mcp.",
  mcp_remote_endpoint_credentials:
    "A URL carrying a username or password is never used. Put the token in an environment variable and name that variable instead — the token then stays in one place you control, rather than in every log that prints the URL.",
  mcp_remote_requires_https:
    "A server outside this machine and your own network must use https. Over plain http the token and every tool call travel in clear text, and that is not something typing a hostname asked for.",
  mcp_remote_metadata_endpoint:
    "That name belongs to a cloud metadata service, which answers with the credentials of the machine Raiker is running on. It is not a tool server.",
  mcp_remote_link_local:
    "That address is link-local. It is where a cloud instance keeps its credential service, not where a tool server lives.",
  mcp_remote_address_forbidden:
    "That address is not one a server can be reached at — it is multicast, reserved, or otherwise not a destination.",
  mcp_remote_host_not_public:
    "That hostname resolves to an address on a private network. A public name answering with a private address is how a request to a tool server becomes a request to your router or a cloud metadata service. If the server really is on your own network, add it by its address or its .internal name.",
  mcp_remote_host_unresolved:
    "That hostname could not be resolved. Check the spelling, and check that this machine has network access.",
  mcp_remote_redirect_untrusted:
    "That server redirected the session to a destination Raiker will not follow. A redirect is re-checked exactly like the original endpoint, so a server cannot send a session somewhere the endpoint itself could not go.",
  mcp_remote_too_many_redirects:
    "That server redirected the session more times than Raiker follows.",
};

/**
 * The sentence for a refused endpoint, or null when this reason code is about
 * something else entirely — in which case the caller's own wording stands.
 */
export function endpointRefusal(reasonCode: string | null | undefined): string | null {
  if (!reasonCode) return null;
  return ENDPOINT_REFUSALS[reasonCode.split(":", 1)[0]] ?? null;
}
