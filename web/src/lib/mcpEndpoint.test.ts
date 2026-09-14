/*
 * RR-MCP-02 — the card used to call three different destinations one name.
 *
 * These assert the same distinctions the runtime makes
 * (`tests/test_mcp_endpoint_policy.py`), because a page that classifies an
 * endpoint differently from the runtime that connects to it is worse than a
 * page that says nothing.
 */
import { describe, expect, it } from "vitest";

import {
  endpointEncrypted,
  endpointRefusal,
  networkClassLabel,
  statedNetworkClass,
} from "./mcpEndpoint";

describe("where a remote MCP server is", () => {
  it("reads the owner's own machine as this machine", () => {
    expect(statedNetworkClass("http://127.0.0.1:3000/mcp")).toBe("loopback");
    expect(statedNetworkClass("http://localhost:8080/mcp")).toBe("loopback");
    expect(statedNetworkClass("http://[::1]:8080/mcp")).toBe("loopback");
  });

  it("reads the owner's own network as their network", () => {
    expect(statedNetworkClass("http://192.168.1.20:3000/mcp")).toBe("private_network");
    expect(statedNetworkClass("http://10.0.0.5/mcp")).toBe("private_network");
    expect(statedNetworkClass("https://172.16.4.9/mcp")).toBe("private_network");
    expect(statedNetworkClass("http://nas.internal/mcp")).toBe("private_network");
    expect(statedNetworkClass("http://tools.home.arpa/mcp")).toBe("private_network");
  });

  it("judges an IPv4-mapped address on the address it really carries", () => {
    expect(statedNetworkClass("http://[::ffff:127.0.0.1]:3000/mcp")).toBe("loopback");
  });

  it("reads anything else as remote", () => {
    expect(statedNetworkClass("https://tools.example.com/mcp")).toBe("public");
    expect(statedNetworkClass("https://203.0.113.10/mcp")).toBe("public");
  });

  it("says nothing about a URL Raiker would not accept", () => {
    expect(statedNetworkClass("ftp://tools.example.com/mcp")).toBeNull();
    expect(statedNetworkClass("not a url")).toBeNull();
    expect(statedNetworkClass("")).toBeNull();
    expect(statedNetworkClass(null)).toBeNull();
  });
});

describe("what the card says", () => {
  it("no longer calls an unencrypted endpoint HTTPS", () => {
    expect(networkClassLabel("http://127.0.0.1:3000/mcp")).toBe(
      "This machine (unencrypted HTTP)",
    );
    expect(networkClassLabel("http://192.168.1.20/mcp")).toBe(
      "Your network (unencrypted HTTP)",
    );
    expect(networkClassLabel("https://tools.example.com/mcp")).toBe("Remote (HTTPS)");
  });

  it("does not guess at an endpoint it cannot read", () => {
    expect(networkClassLabel("gopher://old.example.com")).toBe(
      "Remote (unrecognised endpoint)",
    );
  });

  it("knows whether the wire is encrypted", () => {
    expect(endpointEncrypted("https://tools.example.com/mcp")).toBe(true);
    expect(endpointEncrypted("http://tools.example.com/mcp")).toBe(false);
    expect(endpointEncrypted(null)).toBe(false);
  });
});

describe("what an owner reads when an endpoint is refused", () => {
  it("answers every refusal the runtime can return with a sentence", () => {
    const reasons = [
      "mcp_remote_invalid_endpoint",
      "mcp_remote_endpoint_credentials",
      "mcp_remote_requires_https",
      "mcp_remote_metadata_endpoint",
      "mcp_remote_link_local",
      "mcp_remote_address_forbidden",
      "mcp_remote_host_not_public",
      "mcp_remote_host_unresolved",
      "mcp_remote_redirect_untrusted",
      "mcp_remote_too_many_redirects",
    ];
    for (const reason of reasons) {
      const sentence = endpointRefusal(reason);
      expect(sentence, reason).toBeTruthy();
      expect(sentence?.endsWith("."), reason).toBe(true);
    }
  });

  it("survives the detailed reason code the transport returns for a redirect", () => {
    expect(endpointRefusal("mcp_remote_redirect_untrusted:mcp_remote_host_not_public")).toBe(
      endpointRefusal("mcp_remote_redirect_untrusted"),
    );
  });

  it("leaves a reason code that is about something else alone", () => {
    expect(endpointRefusal("disabled_by_capability_gate")).toBeNull();
    expect(endpointRefusal(null)).toBeNull();
  });
});
