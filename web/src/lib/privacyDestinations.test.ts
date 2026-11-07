import { describe, expect, it } from "vitest";
import { configuredDestinations } from "./privacyDestinations";

const profile = (partial: Record<string, unknown>) => ({
  profile_id: "p",
  provider: "anthropic",
  local_only: false,
  configured: true,
  connection_configured: true,
  model_locations: {},
  ...partial,
});

describe("configuredDestinations (beta plan §6)", () => {
  it("lists each connected hosted provider once, in one model-prompts row", () => {
    const rows = configuredDestinations(
      [profile({}), profile({ profile_id: "q" }), profile({ profile_id: "o", provider: "openai" })],
      null,
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].destination).toBe("Anthropic, OpenAI");
    expect(rows[0].carries).toMatch(/Model prompts/);
  });

  it("skips unconfigured profiles and on-device models", () => {
    const rows = configuredDestinations(
      [
        profile({ configured: false, connection_configured: false }),
        profile({ provider: "ollama", local_only: true, model_locations: { "llama3.2": "device" } }),
      ],
      null,
    );
    expect(rows).toEqual([]);
  });

  it("names the remote host a local runtime's cloud model reaches", () => {
    const rows = configuredDestinations(
      [profile({ provider: "ollama", local_only: true, model_locations: { "gpt-oss:20b-cloud": "ollama.com" } })],
      null,
    );
    expect(rows.map((row) => row.destination)).toEqual(["ollama.com"]);
  });

  it("adds the update channel's host", () => {
    const rows = configuredDestinations([], "https://releases.example/beta.json");
    expect(rows[0]).toMatchObject({ destination: "releases.example", whereLabel: "About & updates" });
  });
});
