// BUG-347 / BUG-358 — remote access in words: every line reads what the
// running host reported, and the form sends only the chosen mode's fields.
import { describe, expect, it } from "vitest";
import { remoteStatus } from "./test-helpers";
import {
  configFrom,
  connectionLabel,
  eventLabel,
  exposureSentence,
  formFrom,
  httpsLabel,
  mfaReadiness,
  proxyExample,
  stateLabel,
} from "./remoteAccess";

const LOCAL = { mode: "local", proxy_kind: "port", proxy_port: null, proxy_socket: null, private_host: null, private_port: null, tls_cert: null, tls_key: null } as const;

describe("remote access labels", () => {
  it("names the state the host reports, never the one asked for", () => {
    expect(stateLabel(remoteStatus())).toBe("Off — this device only");
    expect(stateLabel(remoteStatus({ state: "enabled" }))).toBe("On");
    expect(stateLabel(remoteStatus({ state: "suspended" }))).toBe("Suspended");
    expect(stateLabel(remoteStatus({ state: "pending_restart", desired: { ...LOCAL, mode: "proxy", proxy_port: 8766 } }))).toBe(
      "Waiting for a restart",
    );
    expect(stateLabel(remoteStatus({ state: "pending_restart" }))).toBe("Turning off at restart");
  });

  it("describes the open connection, and nothing when none is open", () => {
    expect(connectionLabel(remoteStatus())).toBe("This device only");
    const open = remoteStatus({ active: { mode: "proxy", address: "unix:/run/raiker/proxy.sock", source: "settings", https_verified: true, refusing: false } });
    expect(connectionLabel(open)).toBe("Reverse proxy · unix:/run/raiker/proxy.sock");
  });

  it("says what two-step sign-in needs", () => {
    expect(mfaReadiness(remoteStatus()).label).toBe("Enrolled");
    expect(mfaReadiness(remoteStatus({ mfa: { enrolled: false, ready: false, accounts_without_mfa: 1, reset_pending: false } })).label).toBe("Required");
    expect(mfaReadiness(remoteStatus({ mfa: { enrolled: true, ready: true, accounts_without_mfa: 0, reset_pending: true } })).label).toBe(
      "Verification needed",
    );
    expect(httpsLabel("not_verified")).toBe("Not verified yet");
    expect(eventLabel("remote_mfa_failed")).toBe("A remote code was wrong");
  });
});

describe("the form", () => {
  it("sends only the chosen mode's fields", () => {
    const form = formFrom({ ...LOCAL, mode: "proxy" });
    expect(form.proxyPort).toBe("8766");
    expect(configFrom(form)).toEqual({ mode: "proxy", proxy_kind: "port", proxy_port: 8766 });
    form.proxyKind = "socket";
    form.proxySocket = " /run/raiker/proxy.sock ";
    expect(configFrom(form)).toEqual({ mode: "proxy", proxy_kind: "socket", proxy_socket: "/run/raiker/proxy.sock" });
    form.mode = "private";
    form.privateHost = "100.101.102.103";
    form.tlsCert = "/c.pem";
    form.tlsKey = "/k.pem";
    expect(configFrom(form)).toEqual({
      mode: "private",
      private_host: "100.101.102.103",
      private_port: 8443,
      tls_cert: "/c.pem",
      tls_key: "/k.pem",
    });
    form.privatePort = "not a port";
    expect(configFrom(form).private_port).toBeNull();
  });

  it("says who will be able to reach Raiker before it is confirmed", () => {
    const form = formFrom({ ...LOCAL, mode: "private", private_host: "10.0.0.5", private_port: 8443 });
    expect(exposureSentence(form)).toBe("Devices on your private network or VPN will be able to open Raiker at https://10.0.0.5:8443.");
    const proxy = formFrom({ ...LOCAL, mode: "proxy", proxy_port: 8766 });
    expect(exposureSentence(proxy)).toContain("127.0.0.1:8766");
    expect(proxyExample(proxy)).toContain("reverse_proxy 127.0.0.1:8766");
    proxy.proxyKind = "socket";
    proxy.proxySocket = "/run/raiker/proxy.sock";
    expect(proxyExample(proxy)).toContain("reverse_proxy unix//run/raiker/proxy.sock");
  });
});
