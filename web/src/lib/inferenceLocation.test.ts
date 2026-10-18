// BUG-340 — a model is described by where it runs, not by where its runtime runs.
import { describe, expect, it } from "vitest";
import { inferenceLocation, inferenceSentence, remoteDestinations } from "./inferenceLocation";

const ollama = {
  provider: "ollama",
  local_only: true,
  model_locations: {
    "llama3:latest": "device",
    "gpt-oss:20b-cloud": "ollama.com",
  },
};

describe("where a model's requests are processed", () => {
  it("trusts the running service's own answer", () => {
    expect(inferenceLocation(ollama, "llama3:latest")).toEqual({ kind: "device" });
    expect(inferenceLocation(ollama, "gpt-oss:20b-cloud")).toEqual({
      kind: "remote",
      destination: "ollama.com",
    });
  });

  it("never calls a Cloud-named model local, even with no service answer", () => {
    const silent = { provider: "ollama", local_only: true };
    expect(inferenceLocation(silent, "deepseek-v4-pro:cloud").kind).toBe("remote");
    expect(inferenceLocation(silent, "gemma4:31b-cloud").kind).toBe("remote");
  });

  it("says a model the service did not describe is unverified, not local", () => {
    expect(inferenceLocation(ollama, "qwen3:8b")).toEqual({ kind: "unknown" });
  });

  it("names the provider for a hosted profile", () => {
    expect(inferenceLocation({ provider: "anthropic", local_only: false }, "claude-haiku-4-5")).toEqual({
      kind: "remote",
      destination: "Anthropic",
    });
  });

  it("claims the device only for a model that runs on it", () => {
    expect(inferenceSentence({ kind: "device" })).toMatch(/runs on this device/);
    expect(inferenceSentence({ kind: "remote", destination: "ollama.com" })).toBe(
      "Its requests are sent to ollama.com, off this device.",
    );
    expect(inferenceSentence({ kind: "unknown" })).not.toMatch(/runs on this device/);
  });

  it("lists each remote host a runtime reaches once", () => {
    expect(remoteDestinations(ollama)).toEqual(["ollama.com"]);
    expect(remoteDestinations({ model_locations: { a: "device" } })).toEqual([]);
    expect(remoteDestinations({})).toEqual([]);
  });
});
